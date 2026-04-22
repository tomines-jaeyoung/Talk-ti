import os
import json
import base64
import re
import time
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# 1. 설정 로드 및 플라스크 앱 초기화
load_dotenv()
app = Flask(__name__)
CORS(app)

# Ollama 모델 설정
OLLAMA_URL = "http://ollama.aikopo.net:8080/api/generate"
OLLAMA_MODEL = "gemma4:31b"

# 메모리 기반 데이터 (실제 프로덕션에서는 DB나 Redis를 권장합니다)
app_state = {
    "registered_tools": [],
    "recent_intent": None,
    "chat_history": [] # 추가된 대화 이력: [{'role': 'user'|'assistant', 'text': '...'}]
}

# --- 1. 시스템 초기화 및 API 등록 ---
@app.route('/api/register', methods=['POST'])
def register_tools():
    """안드로이드 앱이 시작될 때 사용 가능한 기능을 서버에 등록합니다."""
    data = request.json or {}
    tools = data.get('tools', [])
    app_state["registered_tools"] = tools
    app_state["chat_history"] = [] # 초기화 시 대화 이력 리셋
    app_state["recent_intent"] = None
    
    print(f"[서버 초기화] 등록된 도구: {tools}")
    return jsonify({"status": "success", "message": f"{len(tools)}개의 도구가 등록되었습니다."})


# --- 2. 앱 열기 및 인텐트 파악 (STEP 1) ---
@app.route('/api/voice_command', methods=['POST'])
@app.route('/upload/text', methods=['POST'])
def voice_command():
    """어르신의 음성(텍스트)을 분석하여 의도를 파악하고, 부족한 정보가 있으면 되묻습니다."""
    data = request.json or {}
    user_input = data.get('text', '')
    
    # 안드로이드 STT 수신 확인용 서버 로그 출력
    print(f"\n[안드로이드 STT 수신] 전달받은 텍스트: '{user_input}'", flush=True)
    
    # 대화 기록에 사용자 발화 추가
    if user_input:
        app_state["chat_history"].append({"role": "user", "text": user_input})
    
    # 이전 대화 포맷팅 (최근 6개만 참고)
    history_text = "\n".join([f"{msg['role']}: {msg['text']}" for msg in app_state["chat_history"][-6:]])
    
    prompt_text = f"""
    당신은 어르신의 스마트폰 조작을 돕는 인공지능 비서 '똑띠(Talk-ti)' 입니다.
    사용자의 요청을 듣고 어떤 앱을 켜야할지 구체적으로 판단하세요.
    응답은 마크다운 기호 없이 순수 JSON 포맷이어야 합니다.
    절대로 다른 부연 설명이나 인사말, 마크다운(```)을 붙이지 말고 오직 중괄호({{}})로 묶인 JSON 덩어리 하나만 출력하세요.
    
    [핵심 규칙 - 반드시 순차적으로 1개씩만 질문하세요!]
    1. [단계 1: 목적지 확정] 사용자의 목적지가 명확하지 않다면, 현 위치 기준 가장 가까운 "단 1곳의 장소"만 물어보세요. 
       (예: "현재 계신 곳에서 가장 가까운 의정부 삼성병원이 맞으신가요?")
       **절대로 이 단계에서 이동 수단(택시/버스 등)을 같이 묻지 마세요.**
    2. 만약 어르신이 아니라고 하면, 그 다음으로 가까운 다른 1곳의 장소를 묻습니다. (예: "그럼 도봉동 삼성병원이 맞으신가요?")
    3. [단계 2: 이동 수단 확정] 어르신이 장소를 맞다고 확정했을 때 비로소, "그곳으로 가시려면 택시를 부를까요, 아니면 지도 길찾기를 도와드릴까요?" 라고 "이동 수단"을 묻습니다.
    4. [단계 3: 앱 실행] 목적지와 수단이 모두 완전하게 명확해졌을 때 비로소 앱을 실행(status: app_open)합니다.
    
    [이전 대화 내역 (참고용)]
    {history_text}
    
    [응답 포맷 1: 목적지를 1곳씩 소거법으로 물어볼 때 (수단은 묻지 않음!)]
    {{
      "status": "chat",
      "tts_message": "어르신, 현재 계신 곳에서 가장 가까운 의정부 삼성병원이 맞으신가요?"
    }}
    
    [응답 포맷 2: 목적지가 확정된 직후 이동 수단을 물어볼 때]
    {{
      "status": "chat",
      "tts_message": "네, 의정부 삼성병원으로 가시려면 택시를 부를까요, 아니면 버스 길찾기를 해드릴까요?"
    }}
    
    [응답 포맷 3: 목적지와 수단이 모두 확정되어 특정 앱 실행이 필요할 때]
    {{
      "status": "app_open",
      "app_name": "카카오택시",
      "intent": "의정부 삼성병원으로 택시 호출",
      "tts_message": "네, 카카오택시 앱을 켜서 의정부 삼성병원 가는 택시를 불러드릴게요."
    }}
    """
    
    try:
        payload = {
            "model": OLLAMA_MODEL, 
            "prompt": prompt_text,
            "stream": False
        }
        res = requests.post(OLLAMA_URL, json=payload, timeout=120)
        res.raise_for_status()
        response_text = res.json().get('response', '').strip()
            
        # 텍스트 사이에 섞인 JSON만 정규식으로 안전하게 추출
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if match:
            response_text = match.group(0)
            
        parsed_response = json.loads(response_text)
        
        # 인텐트 업데이트 및 어시스턴트 대화 추가
        if "intent" in parsed_response:
            app_state["recent_intent"] = parsed_response["intent"]
            
        if "tts_message" in parsed_response:
            app_state["chat_history"].append({"role": "assistant", "text": parsed_response["tts_message"]})
            
        return jsonify(parsed_response)
        
    except Exception as e:
        print(f"Ollama API or JSON Parsing Error: {e}", flush=True)
        # 만약 response_text 변수가 존재하면 출력하여 원인 파악
        if 'response_text' in locals():
            print(f"LLM Raw Output: {response_text}", flush=True)
        error_msg = "제가 말씀을 잘 이해하지 못했어요. 조용한 곳에서 다시 말씀해 주시겠어요?"
        app_state["chat_history"].append({"role": "assistant", "text": error_msg})
        return jsonify({
            "status": "chat",
            "tts_message": error_msg
        })


# --- 3. 화면 분석 및 자동화 제어 / 오버레이 (STEP 2 & 3) ---
@app.route('/api/screen_analyze', methods=['POST'])
def screen_analyze():
    """안드로이드의 Accessibility 트리(JSON)와 캡처본(Base64)을 받아 분석하고,
       여러 선택지가 있을 경우 어르신께 물어봅니다."""
    ui_elements = []
    screenshot_base64 = ''
    
    # 1. 안드로이드 실제 연동 (Multipart: 이미지 파일 + JSON 폼 데이터)
    if request.files or request.form:
        # 이미지 파일 수신 및 Base64 인코딩 (AI 모델이 Base64를 요구함)
        file = request.files.get('image') or request.files.get('screenshot')
        if file:
            image_bytes = file.read()
            screenshot_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # 윈도우에서 바로 확인할 수 있도록 imgs 폴더에 파일로도 저장
            save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'imgs')
            os.makedirs(save_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            fname = file.filename if file.filename else "screen.png"
            save_path = os.path.join(save_dir, f"{timestamp}_{fname}")
            with open(save_path, 'wb') as f:
                f.write(image_bytes)
            
        # 폼 데이터에서 트리 구조 JSON 파싱
        # 안드로이드에서 'json_data' 또는 'ui_elements' 키로 스트링을 보낸다고 가정
        json_str = request.form.get('json_data') or request.form.get('ui_elements') or '[]'
        try:
            parsed_form = json.loads(json_str)
            ui_elements = parsed_form.get('ui_elements', []) if isinstance(parsed_form, dict) else parsed_form
        except Exception as e:
            print(f"[경고] Multipart JSON 파싱 실패: {e}", flush=True)
            
    # 2. 기존 웹사이트 테스트 호환용 (순수 JSON)
    elif request.is_json:
        data = request.json or {}
        ui_elements = data.get('ui_elements', [])
        screenshot_base64 = data.get('screenshot', '')
    
    # [로그] 안드로이드에서 보낸 UI 트리(접근성 노드) 데이터 확인
    print(f"\n[안드로이드 UI 트리 수신] 총 {len(ui_elements)}개의 UI 요소가 전달되었습니다.", flush=True)
    if ui_elements:
        print(f"[UI 트리 예시] 첫 번째 요소: {ui_elements[0]}", flush=True)
    current_intent = app_state.get("recent_intent", "알 수 없는 작업")
    
    history_text = "\n".join([f"{msg['role']}: {msg['text']}" for msg in app_state["chat_history"][-6:]])
    
    prompt_text = f"""
    당신은 어르신의 스마트폰 조작을 원격으로 돕는 AI 에이전트 '똑띠'입니다.
    현재 사용자의 최종 목적은 '{current_intent}'입니다. 
    
    클라이언트가 제공한 현재 화면의 UI 요소 리스트(JSON) 및 캡처 이미지를 보고 다음 행동을 선택하세요.
    응답은 마크다운 없이 순수 JSON 포맷으로 작성하세요.
    절대로 다른 부연 설명이나 인사말, 마크다운(```)을 붙이지 말고 오직 중괄호({{}})로 묶인 JSON 덩어리 하나만 출력하세요.
    
    [핵심 규칙 - 반드시 순차적으로 1단계씩 소통하세요!]
    1. [소거법 질문] 화면에 여러 선택지(예: 여러 검색 결과, 여러 버스 경로)가 있다면 전체를 읊지 마세요. 무조건 "가장 첫 번째/가장 빠른" 단 1개만 찝어서 물어보세요. (예: "버스로 30분 걸리는 첫 번째 경로로 안내해 드릴까요?") (status: chat)
    2. [1액션 1소통] 사용자가 특정 선택지를 고르거나(예: "두번째 꺼로 해줘"), 앱을 조작할 때 인공지능이 마음대로 클릭(ACTION_CLICK)해버리지 마세요!
    3. 반드시 **지금 당장 눌러야 할 단 1개의 버튼**에만 오버레이 박스를 띄우세요 (status: overlay_command). 그리고 어르신이 화면을 보고 직접 누르실 수 있도록, "빨간색 네모 박스가 쳐진 [버튼이름] 버튼을 눌러주세요" 처럼 매우 직관적이고 친절하게 TTS 문장을 작성하세요.
    4. [ID 기반 제어] 응답 시 JSON 데이터 안에 안드로이드가 준 UI 요소의 고유 ID(`target_id`)와 인덱스(`target_index`)를 반드시 포함하세요.
    5. [교육용 UX 원칙] 어르신의 학습을 위해 버튼 클릭(예: 돋보기 버튼, 확인 버튼 등)은 모두 오버레이로 유도하여 어르신이 직접 누르시게 합니다. 오직 '글자 타이핑'이 필요한 입력창(EditText)에서만 AI가 ACTION_SET_TEXT로 글자를 대신 써줍니다.
    
    [이전 대화 내역 (참조)]
    {history_text}

    [상황 A: 화면에 여러 선택지가 있어 1개만 찝어 물어볼 때]
    {{
        "status": "chat",
        "tts_message": "검색된 경로 중, 버스로 20분 걸리는 첫 번째 빠른 경로로 안내를 시작할까요?"
    }}

    [상황 B: 텍스트 입력창(EditText 등)이 활성화되어 목적지를 타이핑해야 할 때 (자동 텍스트 입력)]
    {{
        "status": "system_action",
        "action_type": "ACTION_SET_TEXT",
        "target_id": "추출한 텍스트 입력창 ID (예: com.kakao.taxi:id/search_bar)",
        "target_index": 15,
        "arguments": "강남 서울병원",
        "tts_message": "해당 목적지가 입력되고 있으니 잠시만 기다려주세요"
    }}

    [상황 C: 사용자가 선택을 완료하여, 해당 버튼 1개를 누르도록 오버레이로 유도할 때]
    {{
        "status": "overlay_command",
        "target_id": "추출한 ID값 (예: com.kakao.taxi:id/btn_call)",
        "target_index": 12,
        "target_text": "호출하기",
        "tts_message": "화면에 빨간색 네모 박스가 쳐진 '호출하기' 버튼을 손가락으로 꾹 눌러주세요."
    }}

    --- 여기서부터가 현재 화면에 대한 데이터입니다 ---
    현재 화면 UI 요소 JSON: {json.dumps(ui_elements, ensure_ascii=False)}
    """
    
    try:
        payload = {
            "model": OLLAMA_MODEL, 
            "prompt": prompt_text,
            "stream": False
        }
        if screenshot_base64:
            payload["images"] = [screenshot_base64]
            
        res = requests.post(OLLAMA_URL, json=payload, timeout=120)
        res.raise_for_status()
        response_text = res.json().get('response', '').strip()
        
        # 텍스트 사이에 섞인 JSON만 정규식으로 안전하게 추출
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if match:
            response_text = match.group(0)
            
        parsed = json.loads(response_text)
        
        # 화면 분석 결과 중 질문이 있다면 chat_history에 추가
        if parsed.get("status") == "chat" and "tts_message" in parsed:
            app_state["chat_history"].append({"role": "assistant", "text": parsed["tts_message"]})
            
        return jsonify(parsed)
        
    except Exception as e:
        print(f"Error during screen analyze with Ollama: {e}", flush=True)
        if 'response_text' in locals():
            print(f"LLM Raw Output: {response_text}", flush=True)
        return jsonify({
            "status": "error",
            "tts_message": "화면을 파악하는 중에 문제가 발생했어요."
        })

@app.route('/upload/image', methods=['POST'])
def upload_image():
    """안드로이드에서 캡처한 화면 이미지를 Multipart(파일) 형태로 수신합니다."""
    # Multipart 폼 데이터에 'image' 키로 파일이 넘어왔는지 확인
    if 'image' not in request.files:
        print("\n[안드로이드 화면 수신 실패] 'image' 키로 전송된 파일이 없습니다.", flush=True)
        return jsonify({"status": "error", "message": "No image file found in multipart data (key should be 'image')"}), 400
        
    file = request.files['image']
    
    if file.filename == '':
        print("\n[안드로이드 화면 수신 실패] 파일 이름이 비어있습니다.", flush=True)
        return jsonify({"status": "error", "message": "Empty filename"}), 400
        
    # 저장할 디렉토리 생성 (Docker 내부 경로 /app/imgs -> 윈도우의 d:\Talk-ti\imgs 로 매핑됨)
    save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'imgs')
    os.makedirs(save_dir, exist_ok=True)
    
    # 중복 방지를 위한 타임스탬프 기반 고유 파일명 생성
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    save_filename = f"{timestamp}_{file.filename}"
    save_path = os.path.join(save_dir, save_filename)
    
    # 실제 파일 저장
    file.save(save_path)
    
    # 서버 로그 출력
    file_size = os.path.getsize(save_path)
    print(f"\n[안드로이드 화면 수신 성공] 윈도우 폴더에 저장 완료: imgs/{save_filename} (크기: {file_size} bytes)", flush=True)
    
    return jsonify({"status": "success", "message": f"Image {save_filename} saved successfully!"})

@app.route('/api/chat_clear', methods=['POST'])
def chat_clear():
    """테스트용 대화 내역 초기화 API"""
    app_state["chat_history"] = []
    app_state["recent_intent"] = None
    return jsonify({"status": "success"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
