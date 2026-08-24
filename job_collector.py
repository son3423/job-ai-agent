import sqlite3
from bs4 import BeautifulSoup


# 1. HTML 파일 읽기
with open("practice_jobs.html", "r", encoding="utf-8") as file:
    html = file.read()


# 2. BeautifulSoup으로 HTML 분석
soup = BeautifulSoup(html, "html.parser")


# 3. 모든 채용공고 찾기
jobs = soup.find_all("div", class_="job")


# 4. 공고 정보를 저장할 빈 리스트
job_list = []


# 5. 각 공고에서 필요한 정보 추출
for job in jobs:

    title = job.find("h2").text
    company = job.find("p", class_="company").text
    location = job.find("p", class_="location").text

    job_data = {
        "title": title,
        "company": company,
        "location": location
    }

    job_list.append(job_data)


# 6. SQLite 데이터베이스 연결
conn = sqlite3.connect("jobs.db")

cursor = conn.cursor()


# 7. jobs 테이블 생성
cursor.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    company TEXT,
    location TEXT,
    UNIQUE(title, company, location)
)
""")


# 8. 추출한 채용공고를 DB에 저장
for job in job_list:

    cursor.execute(
        """
        INSERT OR IGNORE INTO jobs (title, company, location)
        VALUES (?, ?, ?)
        """,
        (
            job["title"],
            job["company"],
            job["location"]
        )
    )


# 9. 저장 확정
conn.commit()


# 10. 데이터베이스 연결 종료
conn.close()


print("채용공고 수집 및 저장 완료!")