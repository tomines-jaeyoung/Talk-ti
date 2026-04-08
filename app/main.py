#밑의 파일들은 , **"내 컴퓨터의 특정 폴더를 도커라는 '가상 컴퓨터' 안에 그대로 복사
# (또는 실시간 동기화)하고, 그 안에서 내가 정한 환경(파이썬 3.12 등)으로 코드를 실행한다"**는 뜻입니다.



import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

# 1. 설정 로드
load_dotenv()
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest")

# 2. 어르신 비서용 프롬프트 (지침서) 설정
prompt = ChatPromptTemplate.from_template("""
당신은 어르신을 모시는 다정한 인공지능 비서 '톡티'입니다.
어르신의 말씀을 듣고 아래 형식으로 답변해 주세요.

[분석 결과]
- 어르신의 현재 기분: (예: 즐거움, 외로움, 필요사항 발생 등)
- 필요한 기능: (예: 기차 예매, 자녀에게 전화, 약 복용 확인 등)

[톡티의 대답]
- 어르신께 드릴 다정한 대답 한마디
---
어르신 말씀: {user_input}
""")

# 3. 테스트 실행 (어르신이 하실 법한 말씀을 넣어보세요)
user_voice_text = "에구, 허리가 좀 아프네.. 우리 아들한테 전화 좀 걸어줄 수 있니?"

# AI에게 물어보기
chain = prompt | llm
response = chain.invoke({"user_input": user_voice_text})

print(response.content)


