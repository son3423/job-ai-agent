import sqlite3
import ollama


# 1. 데이터베이스 연결
conn = sqlite3.connect("full_jobs.db")

cursor = conn.cursor()


# 2. 첫 번째 채용공고 1개 가져오기
cursor.execute("""
SELECT title, company, location, description
FROM jobs
LIMIT 1
""")

job = cursor.fetchone()


# 3. DB 연결 종료
conn.close()


# 4. 가져온 데이터 각각 분리
title = job[0]
company = job[1]
location = job[2]
description = job[3]


# 5. 상세페이지에서 실제 공고 본문만 추출
start_marker = f"{title}\n{company}"

if start_marker in description:
    description = description.split(start_marker, 1)[1]

if "\nLocation:" in description:
    description = description.split("\nLocation:", 1)[0]

description = description.strip()


# 6. Qwen에게 보낼 질문 만들기
prompt = f"""
다음 채용공고를 한국어로 분석해줘.

직무명: {title}
회사명: {company}
근무지역: {location}

채용공고 본문:
{description}

규칙:
- 제공된 내용만 근거로 분석한다.
- 없는 정보는 추측하지 않는다.
- 의미가 불분명한 내용은 억지로 해석하지 않는다.
- 기술명은 원문 표현을 최대한 유지한다.

아래 형식으로 정리해줘.

1. 한줄 요약
2. 주요 업무
3. 요구 역량
4. 기술 키워드
"""


# 7. 로컬 Qwen에게 요청
response = ollama.chat(
    model="qwen3:4b",
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ]
)


# 8. AI 결과 가져오기
summary = response["message"]["content"]


# 9. 결과 출력
print("===== 원본 공고 =====")
print("직무:", title)
print("회사:", company)
print("지역:", location)

print()

print("===== AI에 전달한 실제 공고 본문 =====")
print(description)

print()

print("===== AI 분석 결과 =====")
print(summary)