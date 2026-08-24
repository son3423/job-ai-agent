import sqlite3
import ollama


# =========================================
# 설정
# =========================================

# 한 번 실행할 때 최대 몇 개의 공고를 분석할지 설정
ANALYZE_LIMIT = 3


# =========================================
# 1. 데이터베이스 연결
# =========================================

conn = sqlite3.connect("full_jobs.db")

cursor = conn.cursor()


# =========================================
# 2. ai_summary 컬럼 존재 여부 확인
# =========================================

cursor.execute("PRAGMA table_info(jobs)")

columns = cursor.fetchall()

column_names = [column[1] for column in columns]


# ai_summary 컬럼이 없으면 새로 생성
if "ai_summary" not in column_names:

    cursor.execute("""
    ALTER TABLE jobs
    ADD COLUMN ai_summary TEXT
    """)

    conn.commit()

    print("ai_summary 컬럼 생성 완료!")


# =========================================
# 3. 아직 분석하지 않은 공고 가져오기
# =========================================

cursor.execute("""
SELECT id, title, company, location, description
FROM jobs
WHERE ai_summary IS NULL
LIMIT ?
""", (ANALYZE_LIMIT,))

jobs = cursor.fetchall()


# =========================================
# 4. 분석할 공고가 없는 경우
# =========================================

if len(jobs) == 0:

    print("분석할 새로운 공고가 없습니다.")

    conn.close()

    exit()


# =========================================
# 5. 가져온 공고들을 하나씩 분석
# =========================================

for index, job in enumerate(jobs):

    job_id = job[0]
    title = job[1]
    company = job[2]
    location = job[3]
    description = job[4]


    print()
    print("=" * 50)
    print(f"[{index + 1}/{len(jobs)}] AI 분석 시작")
    print("직무:", title)
    print("회사:", company)
    print("=" * 50)


    # =========================================
    # 6. 실제 공고 본문만 추출
    # =========================================

    start_marker = f"{title}\n{company}"

    if start_marker in description:

        description = description.split(
            start_marker,
            1
        )[1]


    if "\nLocation:" in description:

        description = description.split(
            "\nLocation:",
            1
        )[0]


    description = description.strip()


    # =========================================
    # 7. Qwen에게 전달할 프롬프트 생성
    # =========================================

    prompt = f"""
다음 채용공고를 한국어로 분석해줘.

직무명:
{title}

회사명:
{company}

근무지역:
{location}

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


    # =========================================
    # 8. Qwen에게 분석 요청
    # =========================================

    response = ollama.chat(
        model="qwen3:4b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )


    # =========================================
    # 9. AI 분석 결과 가져오기
    # =========================================

    summary = response["message"]["content"]


    # =========================================
    # 10. 분석 결과 DB에 저장
    # =========================================

    cursor.execute(
        """
        UPDATE jobs
        SET ai_summary = ?
        WHERE id = ?
        """,
        (
            summary,
            job_id
        )
    )


    # 공고 하나가 끝날 때마다 바로 저장
    conn.commit()


    print("AI 분석 및 DB 저장 완료!")


# =========================================
# 11. DB 연결 종료
# =========================================

conn.close()


# =========================================
# 12. 최종 결과
# =========================================

print()
print("==============================")
print("AI 분석 작업 완료")
print("==============================")
print("이번에 분석한 공고:", len(jobs))