import requests
import json

SERVER_URL = "http://127.0.0.1:5000"

def test_voice_command():
    print("========================================")
    print("🎙️ 안드로이드 앱 가상 테스트 클라이언트 🎙️")
    print("========================================")
    print("안드로이드 앱이 없는 상태에서 STT로 변환된 텍스트를")
    print("직접 서버로 전송하여 결과를 확인하는 테스트입니다.\n")
    
    while True:
        text = input("\n가상 STT 입력(어르신 말씀) [종료하려면 q 입력]: ")
        if text.lower() == 'q':
            print("테스트를 종료합니다.")
            break
            
        payload = {"text": text}
        print("\n⏳ 서버로 전송 중...")
        try:
            # 서버의 /api/voice_command 주소로 POST 요청을 보냅니다.
            response = requests.post(f"{SERVER_URL}/api/voice_command", json=payload)
            
            print("\n✅ --- 서버 응답 (JSON) ---")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
            print("----------------------------")
            
        except requests.exceptions.ConnectionError:
            print("\n❌ 서버 연결 실패: 서버(Docker)가 켜져 있는지 확인해주세요!")
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")

if __name__ == "__main__":
    test_voice_command()
