import sqlite3
import re
from playwright.sync_api import sync_playwright


# =========================
# 1. 데이터베이스 연결
# =========================

conn = sqlite3.connect("full_jobs.db")

cursor = conn.cursor()


# =========================
# 2. 테이블 만들기
# =========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    company TEXT,
    location TEXT,
    posted TEXT,
    url TEXT UNIQUE,
    description TEXT
)
""")


# =========================
# 3. Playwright 실행
# =========================

with sync_playwright() as p:

    browser = p.chromium.launch(headless=False)

    page = browser.new_page()


    # =========================
    # 4. 공고 목록 페이지 접속
    # =========================

    page.goto("https://realpython.github.io/fake-jobs/")

    page.wait_for_selector(".card-content")


    # =========================
    # 5. 목록 페이지의 공고 수 확인
    # =========================

    jobs = page.locator(".card-content")

    job_count = jobs.count()

    print("발견한 공고:", job_count)


    # 공고 목록 정보를 먼저 담아둘 리스트
    job_list = []


    # =========================
    # 6. 공고 목록 정보 수집
    # =========================

    for i in range(job_count):

        job = jobs.nth(i)

        title = job.locator(".title").inner_text()

        company = job.locator(".company").inner_text()

        location = job.locator(".location").inner_text().strip()

        url = job.locator(
            "a",
            has_text="Apply"
        ).get_attribute("href")


        job_data = {
            "title": title,
            "company": company,
            "location": location,
            "url": url
        }

        job_list.append(job_data)


    print("목록 정보 수집 완료!")


    # =========================
    # 7. 상세페이지 하나씩 방문
    # =========================

    saved_count = 0


    for i, job in enumerate(job_list):

        print(
            f"[{i + 1}/{job_count}]",
            job["title"]
        )


        # 상세페이지로 이동
        page.goto(job["url"])


        # 페이지 전체 텍스트 가져오기
        body_text = page.locator("body").inner_text()


        # =========================
        # 8. 게시일 추출
        # =========================

        date_match = re.search(
            r"Posted:\s*(\d{4}-\d{2}-\d{2})",
            body_text
        )

        if date_match:
            posted = date_match.group(1)
        else:
            posted = None


        # =========================
        # 9. 상세 본문 가져오기
        # =========================

        description = body_text


        # =========================
        # 10. DB 저장
        # =========================

        cursor.execute(
            """
            INSERT OR IGNORE INTO jobs
            (
                title,
                company,
                location,
                posted,
                url,
                description
            )

            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                job["title"],
                job["company"],
                job["location"],
                posted,
                job["url"],
                description
            )
        )


        if cursor.rowcount == 1:
            saved_count += 1


    # 브라우저 종료
    browser.close()


# =========================
# 11. 데이터베이스 저장
# =========================

conn.commit()


# =========================
# 12. 전체 공고 개수 확인
# =========================

cursor.execute("SELECT COUNT(*) FROM jobs")

total_count = cursor.fetchone()[0]


conn.close()


# =========================
# 13. 결과 출력
# =========================

print()
print("======================")
print("수집 완료!")
print("======================")

print("발견한 공고:", job_count)
print("새로 저장한 공고:", saved_count)
print("DB 전체 공고:", total_count)