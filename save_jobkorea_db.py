import json
import re
import sqlite3


JSON_FILE = "brightdata_jobkorea_latest.json"
DB_FILE = "jobkorea_jobs.db"


# ==========================================
# 잡코리아 공고 고유 ID 추출
# ==========================================

def extract_job_id(url):
    if not url:
        return None

    match = re.search(r"GI_Read/(\d+)", url)

    if match:
        return match.group(1)

    return None


# ==========================================
# JSON 읽기
# ==========================================

with open(
    JSON_FILE,
    "r",
    encoding="utf-8",
) as file:
    jobs = json.load(file)


print("JSON 공고 수:", len(jobs))


# ==========================================
# SQLite 연결
# ==========================================

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source TEXT NOT NULL,
    source_job_id TEXT UNIQUE,

    job_title TEXT,
    company_name TEXT,
    location TEXT,

    career_requirement TEXT,
    education_requirement TEXT,

    posting_date TEXT,
    application_deadline TEXT,

    employment_type TEXT,

    responsibilities TEXT,
    job_description TEXT,

    job_posting_url TEXT,

    ai_summary TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")


# ==========================================
# DB 저장
# ==========================================

saved_count = 0
duplicate_count = 0


for job in jobs:

    url = job.get("job_posting_url")

    source_job_id = extract_job_id(url)

    if not source_job_id:
        print(
            "공고 ID 추출 실패:",
            job.get("job_title")
        )
        continue


    cursor.execute("""
    INSERT OR IGNORE INTO jobs (
        source,
        source_job_id,
        job_title,
        company_name,
        location,
        career_requirement,
        education_requirement,
        posting_date,
        application_deadline,
        employment_type,
        responsibilities,
        job_description,
        job_posting_url
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "JOBKOREA",
        source_job_id,
        job.get("job_title"),
        job.get("company_name"),
        job.get("location"),
        job.get("career_requirement"),
        job.get("education_requirement"),
        job.get("posting_date"),
        job.get("application_deadline"),
        job.get("employment_type"),
        job.get("responsibilities"),
        job.get("job_description"),
        url,
    ))


    if cursor.rowcount == 1:
        saved_count += 1
    else:
        duplicate_count += 1


conn.commit()


# ==========================================
# 총 DB 공고 수
# ==========================================

cursor.execute(
    "SELECT COUNT(*) FROM jobs"
)

total_count = cursor.fetchone()[0]


conn.close()


print()
print("=" * 50)
print("잡코리아 DB 저장 완료")
print("=" * 50)

print("이번 JSON 공고:", len(jobs))
print("새로 저장:", saved_count)
print("중복 제외:", duplicate_count)
print("DB 전체 공고:", total_count)
print()
print("DB 파일:", DB_FILE)