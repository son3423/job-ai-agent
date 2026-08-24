import sqlite3

job_list = [
    {
        "title": "열관리 시스템 개발",
        "company": "현대자동차",
        "location": "경기도 화성"
    },
    {
        "title": "배터리 시스템 개발",
        "company": "현대모비스",
        "location": "경기도 의왕"
    },
    {
        "title": "히트펌프 시스템 개발",
        "company": "한온시스템",
        "location": "대전"
    }
]

conn = sqlite3.connect("jobs.db")

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    company TEXT,
    location TEXT
)
""")

for job in job_list:
    cursor.execute(
        """
        INSERT INTO jobs (title, company, location)
        VALUES (?, ?, ?)
        """,
        (
            job["title"],
            job["company"],
            job["location"]
        )
    )

conn.commit()
conn.close()

print("채용공고 저장 완료!")