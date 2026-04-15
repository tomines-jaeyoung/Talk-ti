import requests

# 1. 교수님이 주신 URL (포트가 없으면 일단 주소만 적습니다)
# 만약 연결 실패가 뜨면 주소 뒤에 :11434를 붙여보세요.
BASE_URL = "http://ollama.aikopo.net" 

def test_ollama_connection():
    # Ollama의 API 경로
    url = f"{BASE_URL}/api/generate"
    
    # 교수님이 지정해주신 모델명 적용
    payload = {
        "model": "gemma4:31b", 
        "prompt": "안녕 똑똑아, 할머니 도와드릴 준비 됐니? 짧게 대답해줘.",
        "stream": False
    }

    print(f"연결 시도 중: {BASE_URL} (모델: gemma4:31b)...")

    try:
        # 타임아웃 10초 설정 (서버가 느릴 수 있음)
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print("✅ 응답 성공!")
            print("똑똑이의 답변:", response.json()['response'])
        else:
            print(f"❌ 서버 에러 (코드 {response.status_code}): {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ 연결 실패: 주소가 잘못되었거나, 학교 네트워크(VPN)가 아닐 수 있습니다.")
        print("팁: 주소 뒤에 :11434를 붙여서 다시 시도해보세요.")
    except Exception as e:
        print(f"⚠️ 기타 에러 발생: {e}")

if __name__ == "__main__":
    test_ollama_connection()