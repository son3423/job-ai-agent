import os
import json
import time
from urllib.parse import quote

import requests
from dotenv import load_dotenv


# ==========================================
# .env 불러오기
# ==========================================

load_dotenv()

API_TOKEN = os.getenv("BRIGHT_DATA_API_TOKEN")
COLLECTOR_ID = os.getenv("BRIGHT_DATA_COLLECTOR_ID")


if not API_TOKEN:
    raise ValueError(
        "BRIGHT_DATA_API_TOKEN이 없습니다. .env 파일을 확인하세요."
    )

if not COLLECTOR_ID:
    raise ValueError(
        "BRIGHT_DATA_COLLECTOR_ID가 없습니다. .env 파일을 확인하세요."
    )


# ==========================================
# 검색 설정
# ==========================================

SEARCH_KEYWORD = "기계공학"

PAGE_NO = 1
MAX_PAGES = 1


search_url = (
    "https://www.jobkorea.co.kr/Search/?stext="
    + quote(SEARCH_KEYWORD)
)


# ==========================================
# Bright Data API 설정
# ==========================================

TRIGGER_URL = (
    "https://api.brightdata.com/dca/trigger"
    f"?collector={COLLECTOR_ID}"
    "&queue_next=1"
)

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}


inputs = [
    {
        "url": search_url,
        "Page_No": PAGE_NO,
        "max_pages": MAX_PAGES,
    }
]


# ==========================================
# 1. Collector 실행
# ==========================================

print("=" * 60)
print("Bright Data JOBKOREA 수집 시작")
print("=" * 60)

print("검색어:", SEARCH_KEYWORD)
print("페이지:", PAGE_NO)
print("최대 페이지:", MAX_PAGES)
print()


response = requests.post(
    TRIGGER_URL,
    headers=HEADERS,
    json=inputs,
    timeout=30,
)

response.raise_for_status()

trigger_result = response.json()

collection_id = trigger_result["collection_id"]

print("Collector 실행 성공!")
print("Collection ID:", collection_id)
print()


# ==========================================
# 2. 결과가 완성될 때까지 기다리기
# ==========================================

dataset_url = (
    "https://api.brightdata.com/dca/dataset"
    f"?id={collection_id}"
)

print("채용공고 수집 중...")
print("완료될 때까지 자동으로 기다립니다.")
print()


while True:

    response = requests.get(
        dataset_url,
        headers={
            "Authorization": f"Bearer {API_TOKEN}"
        },
        timeout=30,
    )

    response.raise_for_status()

    result = response.json()

    # 완료되면 JSON 배열이 반환됨
    if isinstance(result, list):

        print()
        print("수집 완료!")
        print("수집된 레코드:", len(result))

        break

    # 아직 작업 중
    status = result.get("status", "unknown")

    print(
        f"현재 상태: {status} "
        "- 5초 후 다시 확인합니다."
    )

    time.sleep(5)


# ==========================================
# 3. JSON 파일 저장
# ==========================================

output_file = "brightdata_jobkorea_latest.json"

with open(
    output_file,
    "w",
    encoding="utf-8",
) as file:

    json.dump(
        result,
        file,
        ensure_ascii=False,
        indent=2,
    )


print()
print("=" * 60)
print("저장 완료")
print("=" * 60)

print("파일:", output_file)
print("공고 수:", len(result))


# ==========================================
# 4. 첫 번째 공고 미리보기
# ==========================================

if result:

    first_job = result[0]

    print()
    print("=" * 60)
    print("첫 번째 공고 미리보기")
    print("=" * 60)

    print(
        "직무:",
        first_job.get("job_title")
    )

    print(
        "회사:",
        first_job.get("company_name")
    )

    print(
        "경력:",
        first_job.get("career_requirement")
    )

    print(
        "학력:",
        first_job.get("education_requirement")
    )

    print(
        "마감일:",
        first_job.get("application_deadline")
    )

    print()
    print("상세내용:")
    print(
        first_job.get("job_description")
    )