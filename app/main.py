import os
import json
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

# 1. 설정 로드 및 플라스크 앱 초기화
load_dotenv()
app = Flask(__name__)
CORS(app)

# Gemini 모델 설정
llm = ChatGoogleGenerativeAI(model="gemini-flash-latest")

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
def voice_command():
    """어르신의 음성(텍스트)을 분석하여 의도를 파악하고, 부족한 정보가 있으면 되묻습니다."""
    data = request.json or {}
    user_input = data.get('text', '')
    
    # 대화 기록에 사용자 발화 추가
    if user_input:
        app_state["chat_history"].append({"role": "user", "text": user_input})
    
    # 이전 대화 포맷팅 (최근 6개만 참고)
    history_text = "\n".join([f"{msg['role']}: {msg['text']}" for msg in app_state["chat_history"][-6:]])
    
    prompt = ChatPromptTemplate.from_template("""
    당신은 어르신의 스마트폰 조작을 돕는 인공지능 비서 '똑띠(Talk-ti)' 입니다.
    사용자의 요청을 듣고 어떤 앱을 켜야할지 구체적으로 판단하세요.
    응답은 마크다운 기호 없이 순수 JSON 포맷이어야 합니다.
    절대로 다른 부연 설명이나 인사말, 마크다운(```)을 붙이지 말고 오직 중괄호({{}})로 묶인 JSON 덩어리 하나만 출력하세요.
    
    [핵심 규칙]
    1. 사용자의 목적(장소, 이동수단 등)이 하나라도 명확하지 않은 상태에서 무작정 앱을 실행하지 마세요.
    2. '삼성병원' 등 목적지 범위를 좁혀야 할 때는 "소거법(가장 가까운 딱 한 곳만 제시)"을 쓰고, 이와 "동시에" 어떤 앱(이동 수단)을 쓸지도 묶어서 물어보세요.
       (예: "어르신, 현재 계신 곳에서 딱 제일 가까운 [종로구 강북삼성병원]으로 가실 건가요? 가신다면 카카오택시를 부를까요, 아니면 지도 길찾기를 켤까요?")
       만약 어르신이 아니라고 하면, 그 다음 지점을 제시하며 똑같이 수단도 물어보세요.
    3. 목적지와 수단이 모두 완전하게 명확해졌을 때 비로소 앱을 실행(status: app_open)합니다.
    
    [이전 대화 내역 (참고용)]
    {history_text}
    
    [응답 포맷 1: 추가 정보가 필요하여 어르신께 되물어야 할 때]
    {{
      "status": "chat",
      "tts_message": "어르신, 삼성병원으로 가시려면 택시를 부를까요, 아니면 버스 길찾기를 해드릴까요?"
    }}
    
    [응답 포맷 2: 목적이 충분히 구체화되어 특정 앱 실행이 필요할 때]
    {{
      "status": "app_open",
      "app_name": "카카오택시",
      "intent": "서울삼성병원으로 택시 호출",
      "tts_message": "네, 카카오택시 앱을 켜서 삼성병원 가는 택시를 불러드릴게요."
    }}
    
    [응답 포맷 3: 단순 일상 대화 또는 위로가 필요할 때]
    {{
      "status": "chat",
      "tts_message": "아이고, 무릎이 아프시군요. 오늘은 무리하지 마시고 푹 쉬세요."
    }}
    """)
    
    try:
        chain = prompt | llm
        response = chain.invoke({"history_text": history_text})
        
        response_content = response.content
        if isinstance(response_content, list):
            response_text = "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in response_content]).strip()
        else:
            response_text = str(response_content).strip()
            
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
        print(f"JSON Parsing Error: {e}")
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
    data = request.json or {}
    
    ui_elements = data.get('ui_elements', [])
    screenshot_base64 = data.get('screenshot', '')
    current_intent = app_state.get("recent_intent", "알 수 없는 작업")
    
    history_text = "\n".join([f"{msg['role']}: {msg['text']}" for msg in app_state["chat_history"][-6:]])
    
    system_msg = SystemMessage(content=f"""
    당신은 어르신의 스마트폰 조작을 원격으로 돕는 AI 에이전트 '똑띠'입니다.
    현재 사용자의 최종 목적은 '{current_intent}'입니다. 
    
    클라이언트가 제공한 현재 화면의 UI 요소 리스트(JSON) 및 캡처 이미지를 보고 다음 행동을 선택하세요.
    응답은 마크다운 없이 순수 JSON 포맷으로 작성하세요.
    절대로 다른 부연 설명이나 인사말, 마크다운(```)을 붙이지 말고 오직 중괄호({{}})로 묶인 JSON 덩어리 하나만 출력하세요.
    
    [핵심 규칙]
    1. [소거법 질문] 화면에 여러 선택지(예: 길찾기 경로 여러 개, 여러 검색 결과)가 있다면, 전체를 한 번에 나열하지 말고 "가장 합리적인(빠른/가까운) 단 한 가지"만 콕 집어서 물어보세요. (예: "버스로 30분 걸리는 가장 빠른 경로로 안내를 시작할까요?") (status: chat)
    2. [1액션 1소통] 앱을 조작하는 모든 과정(예: 사진 보내기)은 절대로 인공지능이 마음대로 한 번에 클릭(ACTION_CLICK)해버리거나 여러 단계를 한 번에 섞어서 지시하면 안 됩니다! 
    3. 반드시 **지금 당장 눌러야 할 단 1개의 버튼**에만 오버레이 박스를 띄우고(status: overlay_command), 어르신이 직접 누르시도록 음성으로 소통하며 액션을 하나씩 완전히 끊어가세요. (예: "+버튼을 눌러주세요" -> 대기 -> "앨범을 눌러주세요" -> 대기)
    
    [이전 대화 내역 (참조)]
    {history_text}

    [상황 A: 화면에 여러 선택지가 있어 딱 하나만 집어서 물어봐야 할 때 (소거법 질문)]
    {{
        "status": "chat",
        "tts_message": "검색된 경로 중, 버스로 20분 걸리는 가장 빠른 경로로 안내를 시작할까요?"
    }}

    [상황 B: 확정된 텍스트를 대상 입력칸에 써야할 때]
    {{
        "status": "system_action",
        "action_type": "ACTION_SET_TEXT",
        "target_index": 15,
        "target_text": "검색창",
        "arguments": "서울삼성병원",
        "tts_message": "도착지에 서울삼성병원을 입력했어요."
    }}

    [상황 C: 특정 버튼 1개를 누르도록 어르신께 직접 화면 오버레이로 지시하고 액션을 끊을 때]
    {{
        "status": "overlay_command",
        "target_index": 찾아낸 요소의 node_index,
        "target_text": "찾아낸 요소의 기존 text 이름",
        "tts_message": "화면 왼쪽 아래의 ➕(더보기) 버튼을 눌러주세요."
    }}
    """)
    
    content_list = [
        {"type": "text", "text": f"현재 화면 UI 요소 JSON: {json.dumps(ui_elements, ensure_ascii=False)}"}
    ]
    
    if screenshot_base64:
        content_list.append({
            "type": "image_url",
            "image_url": f"data:image/jpeg;base64,{screenshot_base64}"
        })
        
    user_msg = HumanMessage(content=content_list)
    
    try:
        response = llm.invoke([system_msg, user_msg])
        response_content = response.content
        if isinstance(response_content, list):
            response_text = "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in response_content]).strip()
        else:
            response_text = str(response_content).strip()
        
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
        print(f"Error during screen analyze: {e}")
        return jsonify({
            "status": "error",
            "tts_message": "화면을 파악하는 중에 문제가 발생했어요."
        })

@app.route('/api/chat_clear', methods=['POST'])
def chat_clear():
    """테스트용 대화 내역 초기화 API"""
    app_state["chat_history"] = []
    app_state["recent_intent"] = None
    return jsonify({"status": "success"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
