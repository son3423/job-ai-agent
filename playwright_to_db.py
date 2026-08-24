import sqlite3
from playwright.sync_api import sync_playwright


# 1. SQLite 데이터베이스 연결
conn = sqlite3.connect("fake_jobs.db")

cursor = conn.cursor()


# 2. jobs 테이블 생성
cursor.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    company TEXT,
    location TEXT,
    UNIQUE(title, company, location)
)
""")


# 3. Playwright 실행
with sync_playwright() as p:

    browser = p.chromium.launch(headless=False)

    page = browser.new_page()

    # 4. 채용공고 사이트 접속
    page.goto("https://realpython.github.io/fake-jobs/")

    # 공고가 화면에 나타날 때까지 기다림
    page.wait_for_selector(".card-content")


    # 5. 공고 전부 찾기
    jobs = page.locator(".card-content")

    job_count = jobs.count()

    saved_count = 0


    # 6. 공고 하나씩 처리
    for i in range(job_count):

        job = jobs.nth(i)

        title = job.locator(".title").inner_text()
        company = job.locator(".company").inner_text()
        location = job.locator(".location").inner_text()


        # 7. SQLite에 저장
        cursor.execute(
            """
            INSERT OR IGNORE INTO jobs (title, company, location)
            VALUES (?, ?, ?)
            """,
            (
                title,
                company,
                location
            )
        )


        # 실제로 새 데이터가 들어갔으면 +1
        if cursor.rowcount == 1:
            saved_count += 1


    browser.close()


# 8. DB 저장 확정
conn.commit()


# 9. 현재 DB에 공고가 몇 개 있는지 확인
cursor.execute("SELECT COUNT(*) FROM jobs")

total_count = cursor.fetchone()[0]


# 10. DB 연결 종료
conn.close()


print("웹페이지에서 발견한 공고:", job_count)
print("이번에 새로 저장한 공고:", saved_count)
print("DB에 저장된 전체 공고:", total_count)