# 3.11 대신 3.12-slim 사용
FROM python:3.12-slim
# "컴퓨터를 새로 샀는데, 운영체제(OS)로 파이썬 3.12가 이미 깔린 아주 가벼운 버전을 깔아줘." 
# (배경 화면이나 게임 같은 불필요한 건 뺀 버전입니다.)

# 라이브러리 설치를 위해 시스템 패키지 업데이트
#"새 컴퓨터에 git이라는 도구를 설치해줘. 나중에 오픈소스 같은 걸 다운로드할 때 필요하니까."
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
#"앞으로 내가 하는 모든 작업은 /app이라는 이름의 폴더 안에서 할 거야. 
# (윈도우의 '바탕화면' 같은 곳 설정)"
COPY requirements.txt .
#"내 진짜 컴퓨터에 있는 requirements.txt 파일을 방금 만든 도커 안의 /app 폴더로 복사해줘."
RUN pip install --no-cache-dir -r requirements.txt
#"복사된 파일을 보고, 거기 적힌 인공지능 라이브러리(LangChain 등)들을 싹 다 설치해줘."

COPY . .
#"이제 내 진짜 컴퓨터에 있는 나머지 모든 소스 코드(메인 프로그램 등)를 도커 안으로 다 옮겨줘."

# 5000번 포트를 외부에 열어줍니다.
EXPOSE 5000

CMD ["python", "app/main.py"]