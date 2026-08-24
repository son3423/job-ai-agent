import sqlite3


# 1. 데이터베이스 연결
conn = sqlite3.connect("full_jobs.db")

cursor = conn.cursor()


# 2. AI 분석 결과가 저장된 공고 가져오기
cursor.execute("""
SELECT id, title, company, ai_summary
FROM jobs
WHERE ai_summary IS NOT NULL
""")

jobs = cursor.fetchall()


# 3. 결과 출력
for job in jobs:

    job_id = job[0]
    title = job[1]
    company = job[2]
    ai_summary = job[3]

    print("=" * 50)

    print("ID:", job_id)
    print("직무:", title)
    print("회사:", company)

    print()

    print("AI 분석:")
    print(ai_summary)

    print()


# 4. DB 연결 종료
conn.close()