from playwright.sync_api import sync_playwright

with sync_playwright() as p:

    # 1. 브라우저 실행
    browser = p.chromium.launch(headless=False)

    # 2. 새 페이지 열기
    page = browser.new_page()

    # 3. 연습용 채용공고 사이트 접속
    page.goto("https://realpython.github.io/fake-jobs/")

    # 4. 채용공고 카드 전부 찾기
    jobs = page.locator(".card-content")

    # 5. 공고 개수 확인
    job_count = jobs.count()

    print("공고 개수:", job_count)

    # 6. 각 공고를 하나씩 확인
    for i in range(job_count):

        job = jobs.nth(i)

        title = job.locator(".title").inner_text()
        company = job.locator(".company").inner_text()
        location = job.locator(".location").inner_text()

        print(title, "|", company, "|", location)

    # 7. 3초 기다림
    page.wait_for_timeout(3000)

    # 8. 브라우저 종료
    browser.close()