import re
from playwright.sync_api import sync_playwright

with sync_playwright() as p:

    # 1. 브라우저 실행
    browser = p.chromium.launch(headless=False)

    # 2. 새 페이지 생성
    page = browser.new_page()

    # 3. 채용공고 목록 페이지 접속
    page.goto("https://realpython.github.io/fake-jobs/")

    # 4. 첫 번째 공고 선택
    first_job = page.locator(".card-content").nth(0)

    # 5. 목록 페이지에서 정보 가져오기
    title = first_job.locator(".title").inner_text()
    company = first_job.locator(".company").inner_text()
    location = first_job.locator(".location").inner_text().strip()

    # 6. 상세페이지 URL 가져오기
    apply_link = first_job.locator(
        "a",
        has_text="Apply"
    ).get_attribute("href")

    # 7. 상세페이지 이동
    page.goto(apply_link)

    # 8. 상세페이지 전체 글자 가져오기
    body_text = page.locator("body").inner_text()

    # 9. 게시 날짜 추출
    date_match = re.search(
        r"Posted:\s*(\d{4}-\d{2}-\d{2})",
        body_text
    )

    if date_match:
        posted = date_match.group(1)
    else:
        posted = None

    # 10. 결과 출력
    print("===== 채용공고 =====")
    print("제목:", title)
    print("회사:", company)
    print("지역:", location)
    print("게시일:", posted)
    print("URL:", apply_link)

    print("\n===== 상세 본문 =====")
    print(body_text)

    # 11. 3초 기다리기
    page.wait_for_timeout(3000)

    # 12. 브라우저 종료
    browser.close()