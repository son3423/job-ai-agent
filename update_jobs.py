import os
import json
import re
import sqlite3
import time
import hashlib

from datetime import date, datetime
from urllib.parse import quote

import requests
import ollama

from dotenv import load_dotenv


# ============================================================
# 기본 설정
# ============================================================

DB_FILE = "jobkorea_jobs.db"

OUTPUT_FILE = "brightdata_jobkorea_latest.json"

SEARCH_KEYWORD = "기계공학"

PAGE_NO = 1

# Bright Data 크레딧 절약
MAX_PAGES = 1

POLL_INTERVAL = 5

# 최대 20분 대기
POLL_TIMEOUT = 20 * 60


# ============================================================
# 자동 AI 분석 설정
# ============================================================

MODEL_NAME = "qwen3:4b"

# 이 점수 이상인 공고만
# Qwen 자동 상세분석
AUTO_AI_MIN_SCORE = 80

# 혹시 공고가 많이 들어와도
# 한 번에 최대 10개까지만 AI 분석
AUTO_AI_MAX_PER_RUN = 10

AI_ANALYSIS_VERSION = "fast_v1"


# ============================================================
# 기계공학 핵심 키워드
# ============================================================

CORE_MECHANICAL_KEYWORDS = [
    "기계",
    "기구",
    "기계설계",
    "기계 설계",
    "기구설계",
    "기구 설계",
    "생산기술",
    "생산 기술",
    "제조기술",
    "제조 기술",
    "공정기술",
    "공정 기술",
    "공정개발",
    "공정 개발",
    "장비설계",
    "장비 설계",
    "설비기술",
    "설비 기술",
    "구조설계",
    "구조 설계",
    "구조해석",
    "구조 해석",
    "mechanical",
    "mechanical design",
    "design engineer",
    "design engineering",
    "production engineer",
    "manufacturing engineer",
]


# ============================================================
# 기계공학 보조 키워드
# ============================================================

MECHANICAL_SUPPORT_KEYWORDS = [
    "설계",
    "공정",
    "제조",
    "품질",
    "설비",
    "장비",
    "해석",
    "자동차",
    "자동화",
    "로봇",
    "모터",
    "열관리",
    "냉동",
    "공조",
    "hvac",
    "배터리",
    "cae",
    "cad",
    "catia",
    "solidworks",
]


# ============================================================
# 전기 / 전자 중심 키워드
# ============================================================

ELECTRICAL_KEYWORDS = [
    "전장",
    "전기",
    "전자",
    "펌웨어",
    "회로",
    "pcb",
    "제어기 sw",
    "제어기sw",
    "모터드라이버",
    "모터 드라이버",
    "배선",
    "전기판넬",
]


# ============================================================
# 정비 / 유지보수 중심 키워드
# ============================================================

MAINTENANCE_KEYWORDS = [
    "정비",
    "유지보수",
    "유지 보수",
    "수리",
    "설치기사",
    "설치 기사",
    "a/s",
    "as 기사",
]


# ============================================================
# 엔지니어링 성격 키워드
# ============================================================

ENGINEERING_KEYWORDS = [
    "설계",
    "개발",
    "연구",
    "r&d",
    "생산기술",
    "생산 기술",
    "공정기술",
    "공정 기술",
    "공정개발",
    "공정 개발",
    "해석",
    "engineering",
    "engineer",
]


# ============================================================
# 제외 공고
# ============================================================

EXCLUDE_KEYWORDS = [
    "취업캠프",
    "교육생",
    "연수생",
    "국비지원",
    "교육과정",
]


# ============================================================
# 텍스트 기본 처리
# ============================================================

def normalize_text(text):

    if not text:
        return ""

    text = text.lower()

    # "전기계장" 속 "기계" 오탐 방지
    text = text.replace(
        "전기계장",
        ""
    )

    return text


def contains_any(text, keywords):

    text = normalize_text(text)

    for keyword in keywords:

        if keyword.lower() in text:
            return True

    return False


# ============================================================
# 잡코리아 UI 잡음 제거
# ============================================================

def clean_description(text):

    if not text:
        return ""

    noise_texts = [
        "로그인 하고 비슷한 조건의 AI추천공고를 확인해 보세요!",
        "TOP 궁금해요",
        "지도보기",
        "이 기업과 나의 적합도 체크",
        "회사에서 중요하게 생각하는 역량과 가치가 나와 맞는지 알아보기",
        "지금 로그인 하면 나와 회사의 적합도를 비교해볼 수 있어요.",
        "추천공고",
        "기업정보",
    ]

    for noise in noise_texts:

        text = text.replace(
            noise,
            " "
        )

    return " ".join(
        text.split()
    )


# ============================================================
# 공고 내용 Hash
#
# 공고 내용이 변경되면
# 기존 AI 분석을 자동 무효화하기 위함
# ============================================================

def calculate_content_hash(job):

    values = [
        job.get("job_title"),
        job.get("company_name"),
        job.get("career_requirement"),
        job.get("education_requirement"),
        job.get("employment_type"),
        job.get("responsibilities"),
        job.get("job_description"),
        job.get("application_deadline"),
    ]

    combined = "\n".join(
        str(value or "")
        for value in values
    )

    return hashlib.sha256(
        combined.encode("utf-8")
    ).hexdigest()


# ============================================================
# Bright Data 응답
#
# JSON / JSON Array / NDJSON 모두 대응
# ============================================================

def parse_dataset_response(response):

    text = response.text.strip()

    if not text:
        return None


    # --------------------------------------------------------
    # 일반 JSON
    # --------------------------------------------------------

    try:

        return json.loads(text)

    except json.JSONDecodeError:
        pass


    # --------------------------------------------------------
    # NDJSON
    # --------------------------------------------------------

    rows = []

    for line_number, line in enumerate(
        text.splitlines(),
        start=1
    ):

        line = line.strip()

        if not line:
            continue

        try:

            value = json.loads(line)

        except json.JSONDecodeError as error:

            raise ValueError(
                f"NDJSON 파싱 실패 "
                f"(line {line_number}): "
                f"{error}"
            )


        if isinstance(
            value,
            list
        ):

            rows.extend(
                value
            )

        else:

            rows.append(
                value
            )


    return rows


# ============================================================
# Bright Data 수집
# ============================================================

def collect_jobkorea():

    load_dotenv()


    api_token = os.getenv(
        "BRIGHT_DATA_API_TOKEN"
    )


    collector_id = os.getenv(
        "BRIGHT_DATA_COLLECTOR_ID"
    )


    if not api_token:

        raise ValueError(
            "BRIGHT_DATA_API_TOKEN이 없습니다."
        )


    if not collector_id:

        raise ValueError(
            "BRIGHT_DATA_COLLECTOR_ID가 없습니다."
        )


    search_url = (
        "https://www.jobkorea.co.kr/Search/?stext="
        + quote(SEARCH_KEYWORD)
    )


    trigger_url = (
        "https://api.brightdata.com/dca/trigger"
        f"?collector={collector_id}"
        "&queue_next=1"
    )


    headers = {
        "Authorization":
            f"Bearer {api_token}",

        "Content-Type":
            "application/json",
    }


    inputs = [
        {
            "url": search_url,
            "Page_No": PAGE_NO,
            "max_pages": MAX_PAGES,
        }
    ]


    print()
    print("=" * 70)
    print("1. Bright Data 잡코리아 수집")
    print("=" * 70)

    print(
        "검색어:",
        SEARCH_KEYWORD
    )

    print(
        "최대 페이지:",
        MAX_PAGES
    )

    print()
    print(
        "Collector 실행 요청..."
    )


    response = requests.post(
        trigger_url,
        headers=headers,
        json=inputs,
        timeout=60,
    )


    if not response.ok:

        raise RuntimeError(
            "Bright Data Collector 실행 실패\n"
            f"HTTP {response.status_code}\n"
            f"{response.text[:500]}"
        )


    trigger_result = (
        response.json()
    )


    collection_id = (
        trigger_result.get(
            "collection_id"
        )
    )


    if not collection_id:

        raise RuntimeError(
            "collection_id를 찾지 못했습니다."
        )


    print(
        "Collection ID:",
        collection_id
    )


    dataset_url = (
        "https://api.brightdata.com/dca/dataset"
        f"?id={collection_id}"
    )


    dataset_headers = {
        "Authorization":
            f"Bearer {api_token}"
    }


    print()
    print(
        "채용공고 수집 완료를 기다립니다..."
    )


    start_time = (
        time.monotonic()
    )


    while True:

        elapsed = (
            time.monotonic()
            - start_time
        )


        if elapsed > POLL_TIMEOUT:

            raise TimeoutError(
                "Bright Data 수집이 "
                "20분 안에 완료되지 않았습니다."
            )


        response = requests.get(
            dataset_url,
            headers=dataset_headers,
            timeout=60,
        )


        if not response.ok:

            raise RuntimeError(
                "Bright Data 결과 조회 실패\n"
                f"HTTP {response.status_code}\n"
                f"{response.text[:500]}"
            )


        result = (
            parse_dataset_response(
                response
            )
        )


        if result is None:

            print(
                f"아직 결과 없음 - "
                f"{POLL_INTERVAL}초 후 재확인"
            )

            time.sleep(
                POLL_INTERVAL
            )

            continue


        # ----------------------------------------------------
        # 아직 수집 중
        # ----------------------------------------------------

        if isinstance(
            result,
            dict
        ):

            if isinstance(
                result.get("data"),
                list
            ):

                result = (
                    result["data"]
                )

                break


            status = str(
                result.get(
                    "status",
                    "unknown"
                )
            ).lower()


            if status in [
                "failed",
                "error",
                "cancelled",
                "canceled",
            ]:

                raise RuntimeError(
                    f"Bright Data 수집 실패: "
                    f"{result}"
                )


            print(
                f"현재 상태: {status} "
                f"- {POLL_INTERVAL}초 후 재확인"
            )


            time.sleep(
                POLL_INTERVAL
            )

            continue


        # ----------------------------------------------------
        # 완료
        # ----------------------------------------------------

        if isinstance(
            result,
            list
        ):

            break


        raise RuntimeError(
            "예상하지 못한 Bright Data 응답입니다."
        )


    print()
    print(
        "수집 완료!"
    )


    print(
        "원본 레코드:",
        len(result)
    )


    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2,
        )


    print(
        "JSON 저장:",
        OUTPUT_FILE
    )


    return result


# ============================================================
# 잡코리아 공고 ID 추출
# ============================================================

def extract_job_id(url):

    if not url:
        return None


    match = re.search(
        r"/GI_Read/(\d+)",
        url
    )


    if match:

        return match.group(1)


    return None


# ============================================================
# DB 준비
# ============================================================

def prepare_database():

    conn = sqlite3.connect(
        DB_FILE
    )

    cursor = conn.cursor()


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (

        id INTEGER
            PRIMARY KEY AUTOINCREMENT,

        source TEXT
            NOT NULL,

        source_job_id TEXT
            UNIQUE,

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

        content_hash TEXT,

        ai_job_category TEXT,
        ai_major_fit TEXT,
        ai_entry_level_fit TEXT,
        ai_interest_fit TEXT,

        ai_fit_score INTEGER,

        ai_score_breakdown TEXT,
        ai_detail_check TEXT,

        ai_summary TEXT,
        ai_main_tasks TEXT,
        ai_requirements TEXT,
        ai_preferred TEXT,
        ai_skills TEXT,

        ai_analysis_version TEXT,

        created_at TIMESTAMP
            DEFAULT CURRENT_TIMESTAMP
    )
    """)


    cursor.execute(
        "PRAGMA table_info(jobs)"
    )


    existing_columns = {
        row[1]
        for row in cursor.fetchall()
    }


    required_columns = {

        "content_hash":
            "TEXT",

        "ai_job_category":
            "TEXT",

        "ai_major_fit":
            "TEXT",

        "ai_entry_level_fit":
            "TEXT",

        "ai_interest_fit":
            "TEXT",

        "ai_fit_score":
            "INTEGER",

        "ai_score_breakdown":
            "TEXT",

        "ai_detail_check":
            "TEXT",

        "ai_summary":
            "TEXT",

        "ai_main_tasks":
            "TEXT",

        "ai_requirements":
            "TEXT",

        "ai_preferred":
            "TEXT",

        "ai_skills":
            "TEXT",

        "ai_analysis_version":
            "TEXT",
    }


    for (
        column_name,
        column_type
    ) in required_columns.items():

        if (
            column_name
            not in existing_columns
        ):

            cursor.execute(
                f"""
                ALTER TABLE jobs
                ADD COLUMN
                {column_name}
                {column_type}
                """
            )


    conn.commit()
    conn.close()


# ============================================================
# DB 저장
# ============================================================

def save_jobs_to_database(jobs):

    prepare_database()


    conn = sqlite3.connect(
        DB_FILE
    )

    cursor = conn.cursor()


    new_count = 0
    updated_count = 0
    duplicate_count = 0
    failed_count = 0
    changed_count = 0


    seen_ids = set()


    for job in jobs:

        url = (
            job.get(
                "job_posting_url"
            )
            or
            job.get(
                "product_page_url"
            )
        )


        source_job_id = (
            extract_job_id(
                url
            )
        )


        if not source_job_id:

            failed_count += 1
            continue


        # ----------------------------------------------------
        # 같은 수집 결과 안의 중복
        # ----------------------------------------------------

        if source_job_id in seen_ids:

            duplicate_count += 1
            continue


        seen_ids.add(
            source_job_id
        )


        new_hash = (
            calculate_content_hash(
                job
            )
        )


        cursor.execute("""
        SELECT
            id,
            content_hash

        FROM jobs

        WHERE
            source = 'JOBKOREA'
            AND source_job_id = ?
        """, (
            source_job_id,
        ))


        existing = (
            cursor.fetchone()
        )


        # ----------------------------------------------------
        # 기존 공고
        # ----------------------------------------------------

        if existing:

            existing_id = existing[0]
            old_hash = existing[1]


            # 이전에 hash가 존재하고
            # 새 hash와 달라졌으면
            # 공고 내용 변경으로 판단
            content_changed = (
                old_hash is not None
                and
                old_hash != new_hash
            )


            if content_changed:

                changed_count += 1


                # 기존 AI 분석을 무효화
                #
                # 요약 텍스트는 남겨두지만
                # app.py에서는 version이 없으면
                # 최신 분석으로 표시하지 않음
                cursor.execute("""
                UPDATE jobs

                SET
                    ai_analysis_version = NULL

                WHERE id = ?
                """, (
                    existing_id,
                ))


            cursor.execute("""
            UPDATE jobs

            SET
                job_title = ?,
                company_name = ?,
                location = ?,
                career_requirement = ?,
                education_requirement = ?,
                posting_date = ?,
                application_deadline = ?,
                employment_type = ?,
                responsibilities = ?,
                job_description = ?,
                job_posting_url = ?,
                content_hash = ?

            WHERE id = ?
            """, (

                job.get(
                    "job_title"
                ),

                job.get(
                    "company_name"
                ),

                job.get(
                    "location"
                ),

                job.get(
                    "career_requirement"
                ),

                job.get(
                    "education_requirement"
                ),

                job.get(
                    "posting_date"
                ),

                job.get(
                    "application_deadline"
                ),

                job.get(
                    "employment_type"
                ),

                job.get(
                    "responsibilities"
                ),

                job.get(
                    "job_description"
                ),

                url,

                new_hash,

                existing_id,
            ))


            updated_count += 1


        # ----------------------------------------------------
        # 신규 공고
        # ----------------------------------------------------

        else:

            cursor.execute("""
            INSERT INTO jobs (

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

                job_posting_url,

                content_hash

            )
            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            """, (

                "JOBKOREA",

                source_job_id,

                job.get(
                    "job_title"
                ),

                job.get(
                    "company_name"
                ),

                job.get(
                    "location"
                ),

                job.get(
                    "career_requirement"
                ),

                job.get(
                    "education_requirement"
                ),

                job.get(
                    "posting_date"
                ),

                job.get(
                    "application_deadline"
                ),

                job.get(
                    "employment_type"
                ),

                job.get(
                    "responsibilities"
                ),

                job.get(
                    "job_description"
                ),

                url,

                new_hash,
            ))


            new_count += 1


    conn.commit()


    cursor.execute("""
    SELECT COUNT(*)

    FROM jobs

    WHERE source = 'JOBKOREA'
    """)


    total_count = (
        cursor.fetchone()[0]
    )


    conn.close()


    print()
    print("=" * 70)
    print("2. SQLite 저장")
    print("=" * 70)


    print(
        "신규 공고:",
        new_count
    )


    print(
        "기존 공고 갱신:",
        updated_count
    )


    print(
        "내용 변경 감지:",
        changed_count
    )


    print(
        "수집 결과 내부 중복:",
        duplicate_count
    )


    print(
        "ID 추출 실패:",
        failed_count
    )


    print(
        "DB 전체 잡코리아 공고:",
        total_count
    )


# ============================================================
# 마감 여부
# ============================================================

def deadline_is_open(deadline):

    if not deadline:
        return True


    try:

        deadline_date = (
            datetime.strptime(
                deadline[:10],
                "%Y-%m-%d"
            ).date()
        )


        return (
            deadline_date
            >= date.today()
        )


    except Exception:

        return True


# ============================================================
# 1차 필터 점수
# ============================================================

def calculate_filter_score(
    title,
    responsibilities,
    description,
    employment_type
):

    title = normalize_text(
        title
    )


    responsibilities = normalize_text(
        responsibilities
    )


    description = normalize_text(
        description
    )


    employment_type = normalize_text(
        employment_type
    )


    exclude_text = (
        f"{title} "
        f"{employment_type}"
    )


    for keyword in EXCLUDE_KEYWORDS:

        if keyword.lower() in exclude_text:

            return -100


    score = 0


    # 제목
    for keyword in CORE_MECHANICAL_KEYWORDS:

        if keyword.lower() in title:
            score += 5


    for keyword in MECHANICAL_SUPPORT_KEYWORDS:

        if keyword.lower() in title:
            score += 2


    # 모집분야
    for keyword in CORE_MECHANICAL_KEYWORDS:

        if keyword.lower() in responsibilities:
            score += 4


    for keyword in MECHANICAL_SUPPORT_KEYWORDS:

        if keyword.lower() in responsibilities:
            score += 1


    # 상세본문
    for keyword in CORE_MECHANICAL_KEYWORDS:

        if keyword.lower() in description:
            score += 1


    return score


# ============================================================
# 경력직 전용 제외
# ============================================================

def career_ok(career):

    if not career:
        return True


    text = career.lower()


    if "경력무관" in text:
        return True


    if "신입" in text:
        return True


    if "경력" in text:
        return False


    return True


# ============================================================
# 신입 지원 가능성
# ============================================================

def determine_entry_fit(career):

    if not career:
        return "확인 필요"


    text = career.lower()


    if "경력무관" in text:

        return "지원 가능"


    if "신입" in text:

        years = re.findall(
            r"(\d+)\s*년\s*이상",
            text
        )


        if years:

            return "확인 필요"


        return "지원 가능"


    if "경력" in text:

        return "지원 어려움"


    return "확인 필요"


# ============================================================
# 기계공학 전공 연관성
# ============================================================

def determine_major_fit(
    title,
    responsibilities
):

    text = normalize_text(
        f"{title or ''} "
        f"{responsibilities or ''}"
    )


    core_hit = (
        contains_any(
            text,
            CORE_MECHANICAL_KEYWORDS
        )
    )


    support_hit = (
        contains_any(
            text,
            MECHANICAL_SUPPORT_KEYWORDS
        )
    )


    electrical_hit = (
        contains_any(
            text,
            ELECTRICAL_KEYWORDS
        )
    )


    # 전장/전자 중심이면 하향
    if (
        electrical_hit
        and
        not core_hit
    ):

        if support_hit:

            return "중간"


        return "낮음"


    if core_hit:

        return "높음"


    if support_hit:

        return "중간"


    return "낮음"


# ============================================================
# 관심직무 연관성
# ============================================================

def determine_interest_fit(
    title,
    responsibilities
):

    text = normalize_text(
        f"{title or ''} "
        f"{responsibilities or ''}"
    )


    strong_interest_keywords = [
        "기계설계",
        "기계 설계",
        "기구설계",
        "기구 설계",
        "생산기술",
        "생산 기술",
        "제조기술",
        "제조 기술",
        "공정기술",
        "공정 기술",
        "공정개발",
        "공정 개발",
        "열관리",
        "냉동",
        "공조",
        "hvac",
        "배터리",
        "자동화",
        "design engineer",
        "design engineering",
        "mechanical design",
        "production engineer",
        "manufacturing engineer",
        "구조설계",
        "구조 설계",
        "구조해석",
        "구조 해석",
    ]


    normal_interest_keywords = [
        "r&d",
        "연구",
        "개발",
        "설계",
        "품질",
        "자동차",
        "설비",
        "로봇",
        "모터",
    ]


    maintenance_hit = (
        contains_any(
            text,
            MAINTENANCE_KEYWORDS
        )
    )


    engineering_hit = (
        contains_any(
            text,
            ENGINEERING_KEYWORDS
        )
    )


    # 단순 정비/유지보수
    if (
        maintenance_hit
        and
        not engineering_hit
    ):

        return "낮음"


    electrical_hit = (
        contains_any(
            text,
            ELECTRICAL_KEYWORDS
        )
    )


    # 전장/전자 중심
    if electrical_hit:

        direct_hit = (
            contains_any(
                text,
                strong_interest_keywords
            )
        )


        if not direct_hit:

            return "중간"


    # 직접 관심직무
    for keyword in strong_interest_keywords:

        if keyword.lower() in text:

            return "높음"


    hits = 0


    for keyword in normal_interest_keywords:

        if keyword.lower() in text:

            hits += 1


    if hits >= 2:

        return "높음"


    if hits == 1:

        return "중간"


    return "낮음"


# ============================================================
# 복수 직무 공고
# ============================================================

def detect_multi_role(
    title,
    responsibilities
):

    title_text = (
        title or ""
    ).lower()


    responsibilities_text = (
        responsibilities or ""
    ).lower()


    for word in [
        "부문별",
        "직무별",
    ]:

        if word in title_text:

            return True


    roles = [
        role.strip()

        for role
        in responsibilities_text.split(",")

        if role.strip()
    ]


    if len(roles) >= 4:

        return True


    return False


# ============================================================
# 고용 형태 점수
# ============================================================

def calculate_employment_score(
    employment_type,
    description
):

    employment = (
        employment_type or ""
    ).lower()


    description = (
        description or ""
    ).lower()


    if "정규직" in employment:

        return 10


    if (
        "인턴" in employment
        and
        "정규직 전환 가능"
        in description
    ):

        return 7


    if "인턴" in employment:

        return 5


    if "계약직" in employment:

        return 4


    return 3


# ============================================================
# 최종 적합도 점수
# ============================================================

def calculate_final_score(
    major_fit,
    entry_fit,
    interest_fit,
    employment_type,
    description,
    multi_role
):

    major_table = {
        "높음": 35,
        "중간": 20,
        "낮음": 5,
    }


    entry_table = {
        "지원 가능": 30,
        "확인 필요": 15,
        "지원 어려움": 0,
    }


    interest_table = {
        "높음": 25,
        "중간": 15,
        "낮음": 5,
    }


    major_score = (
        major_table[
            major_fit
        ]
    )


    entry_score = (
        entry_table[
            entry_fit
        ]
    )


    interest_score = (
        interest_table[
            interest_fit
        ]
    )


    employment_score = (
        calculate_employment_score(
            employment_type,
            description
        )
    )


    multi_role_penalty = (
        5
        if multi_role
        else 0
    )


    total = (
        major_score
        + entry_score
        + interest_score
        + employment_score
        - multi_role_penalty
    )


    total = max(
        0,
        min(
            100,
            total
        )
    )


    breakdown = {
        "major":
            major_score,

        "entry":
            entry_score,

        "interest":
            interest_score,

        "employment":
            employment_score,

        "multi_role_penalty":
            -multi_role_penalty,
    }


    return total, breakdown


# ============================================================
# DB 적합도 재계산
# ============================================================

def recalculate_scores():

    conn = sqlite3.connect(
        DB_FILE
    )

    cursor = conn.cursor()


    # --------------------------------------------------------
    # 추천 판단만 초기화
    #
    # Qwen 분석 결과는 유지
    # --------------------------------------------------------

    cursor.execute("""
    UPDATE jobs

    SET
        ai_major_fit = NULL,
        ai_entry_level_fit = NULL,
        ai_interest_fit = NULL,
        ai_fit_score = NULL,
        ai_score_breakdown = NULL,
        ai_detail_check = NULL

    WHERE source = 'JOBKOREA'
    """)


    cursor.execute("""
    SELECT
        id,
        job_title,
        company_name,
        career_requirement,
        employment_type,
        responsibilities,
        job_description,
        application_deadline

    FROM jobs

    WHERE source = 'JOBKOREA'
    """)


    jobs = (
        cursor.fetchall()
    )


    results = []


    for job in jobs:

        (
            job_id,
            title,
            company,
            career,
            employment_type,
            responsibilities,
            description,
            deadline,
        ) = job


        # 마감공고 제외
        if not deadline_is_open(
            deadline
        ):

            continue


        # 경력직 전용 제외
        if not career_ok(
            career
        ):

            continue


        filter_score = (
            calculate_filter_score(
                title,
                responsibilities,
                description,
                employment_type,
            )
        )


        if filter_score < 4:

            continue


        major_fit = (
            determine_major_fit(
                title,
                responsibilities
            )
        )


        entry_fit = (
            determine_entry_fit(
                career
            )
        )


        interest_fit = (
            determine_interest_fit(
                title,
                responsibilities
            )
        )


        multi_role = (
            detect_multi_role(
                title,
                responsibilities
            )
        )


        detail_check = (
            "세부직무 확인 필요"
            if multi_role
            else "단일직무"
        )


        (
            final_score,
            breakdown
        ) = calculate_final_score(

            major_fit,

            entry_fit,

            interest_fit,

            employment_type,

            description,

            multi_role,
        )


        cursor.execute("""
        UPDATE jobs

        SET
            ai_major_fit = ?,
            ai_entry_level_fit = ?,
            ai_interest_fit = ?,
            ai_fit_score = ?,
            ai_score_breakdown = ?,
            ai_detail_check = ?

        WHERE id = ?
        """, (

            major_fit,

            entry_fit,

            interest_fit,

            final_score,

            json.dumps(
                breakdown,
                ensure_ascii=False
            ),

            detail_check,

            job_id,
        ))


        results.append({

            "id":
                job_id,

            "title":
                title,

            "company":
                company,

            "score":
                final_score,

            "entry":
                entry_fit,

            "detail":
                detail_check,
        })


    conn.commit()
    conn.close()


    results.sort(
        key=lambda x:
            x["score"],
        reverse=True
    )


    print()
    print("=" * 70)
    print("3. 적합도 자동 재계산")
    print("=" * 70)


    print(
        "현재 추천 공고:",
        len(results)
    )


    print()


    for index, job in enumerate(
        results,
        start=1
    ):

        print(
            f"[{index}] "
            f"{job['score']}점 | "
            f"{job['title']} "
            f"- {job['company']}"
        )


    return results


# ============================================================
# Qwen JSON 응답 파싱
# ============================================================

def parse_ai_json(text):

    text = text.strip()


    try:

        return json.loads(
            text
        )

    except json.JSONDecodeError:
        pass


    start = text.find("{")
    end = text.rfind("}")


    if (
        start != -1
        and end != -1
        and end > start
    ):

        return json.loads(
            text[
                start:end + 1
            ]
        )


    raise ValueError(
        "Qwen 응답에서 JSON을 찾지 못했습니다."
    )


# ============================================================
# 리스트 안전 처리
# ============================================================

def ensure_list(value):

    if isinstance(
        value,
        list
    ):

        return value


    if value is None:

        return []


    return [
        str(value)
    ]


# ============================================================
# 공고 1개 Qwen 분석
# ============================================================

def analyze_job_with_qwen(job):

    description = clean_description(
        job["job_description"]
    )


    # 속도 최적화
    description_for_ai = (
        description[:1400]
    )


    prompt = f"""
아래 채용공고에서 채용 정보를 구조적으로 추출하라.

중요 규칙:

1. 채용공고에 실제로 존재하는 정보만 사용한다.
2. 없는 내용을 추측하지 않는다.
3. 정보가 없으면 빈 배열 []로 반환한다.
4. 지원자의 경험이나 능력을 임의로 만들지 않는다.
5. 반드시 JSON만 반환한다.

직무명:
{job["job_title"]}

회사:
{job["company_name"]}

경력:
{job["career_requirement"]}

학력:
{job["education_requirement"]}

고용형태:
{job["employment_type"]}

모집분야:
{job["responsibilities"]}

상세내용:
{description_for_ai}


다음 JSON 형식으로 반환한다.

{{
    "job_category": "직무 분류",

    "summary": "채용공고 한 줄 요약",

    "main_tasks": [
        "실제 공고에서 확인되는 주요 업무"
    ],

    "requirements": [
        "실제 공고에서 확인되는 지원 자격"
    ],

    "preferred": [
        "실제 공고에서 확인되는 우대 사항"
    ],

    "skills": [
        "실제 공고에서 확인되는 기술 또는 전문분야"
    ]
}}
"""


    response = ollama.chat(

        model=MODEL_NAME,

        messages=[
            {
                "role":
                    "user",

                "content":
                    prompt,
            }
        ],

        format="json",

        think=False,

        options={
            "temperature":
                0,

            "num_predict":
                600,
        },
    )


    ai_text = (
        response[
            "message"
        ][
            "content"
        ]
    )


    analysis = (
        parse_ai_json(
            ai_text
        )
    )


    return {

        "job_category":
            analysis.get(
                "job_category"
            )
            or
            "확인 필요",

        "summary":
            analysis.get(
                "summary"
            )
            or
            "요약 정보 없음",

        "main_tasks":
            ensure_list(
                analysis.get(
                    "main_tasks"
                )
            ),

        "requirements":
            ensure_list(
                analysis.get(
                    "requirements"
                )
            ),

        "preferred":
            ensure_list(
                analysis.get(
                    "preferred"
                )
            ),

        "skills":
            ensure_list(
                analysis.get(
                    "skills"
                )
            ),
    }


# ============================================================
# 자동 AI 분석
# ============================================================

def auto_analyze_jobs():

    conn = sqlite3.connect(
        DB_FILE
    )


    conn.row_factory = (
        sqlite3.Row
    )


    cursor = conn.cursor()


    # --------------------------------------------------------
    # 핵심 조건
    #
    # 1. 추천 점수 80점 이상
    # 2. 최신 분석이 없는 공고
    #
    # 즉 같은 공고를 매일 다시 분석하지 않음
    # --------------------------------------------------------

    cursor.execute("""
    SELECT
        id,

        job_title,
        company_name,

        career_requirement,
        education_requirement,

        employment_type,

        responsibilities,
        job_description,

        ai_fit_score,

        ai_analysis_version

    FROM jobs

    WHERE
        source = 'JOBKOREA'

        AND ai_fit_score >= ?

        AND ai_detail_check
            IS NOT NULL

        AND (
            ai_analysis_version IS NULL
            OR ai_analysis_version != ?
        )

    ORDER BY
        ai_fit_score DESC

    LIMIT ?
    """, (

        AUTO_AI_MIN_SCORE,

        AI_ANALYSIS_VERSION,

        AUTO_AI_MAX_PER_RUN,
    ))


    rows = (
        cursor.fetchall()
    )


    jobs = [
        dict(row)
        for row in rows
    ]


    print()
    print("=" * 70)
    print("4. Qwen 자동 상세 분석")
    print("=" * 70)


    print(
        f"자동 분석 기준: "
        f"{AUTO_AI_MIN_SCORE}점 이상"
    )


    print(
        "이번 실행 AI 분석 대상:",
        len(jobs)
    )


    # 분석할 공고 없음
    if not jobs:

        print()
        print(
            "새로 분석할 공고가 없습니다."
        )

        conn.close()

        return {
            "success":
                0,

            "failed":
                0,
        }


    success_count = 0
    failed_count = 0


    for index, job in enumerate(
        jobs,
        start=1
    ):

        print()
        print("-" * 70)


        print(
            f"[{index}/{len(jobs)}] "
            f"{job['ai_fit_score']}점 | "
            f"{job['job_title']}"
        )


        print(
            "회사:",
            job["company_name"]
        )


        print(
            "Qwen 분석 중..."
        )


        start_time = (
            time.monotonic()
        )


        try:

            analysis = (
                analyze_job_with_qwen(
                    job
                )
            )


            cursor.execute("""
            UPDATE jobs

            SET
                ai_job_category = ?,
                ai_summary = ?,
                ai_main_tasks = ?,
                ai_requirements = ?,
                ai_preferred = ?,
                ai_skills = ?,
                ai_analysis_version = ?

            WHERE id = ?
            """, (

                analysis[
                    "job_category"
                ],

                analysis[
                    "summary"
                ],

                json.dumps(
                    analysis[
                        "main_tasks"
                    ],
                    ensure_ascii=False
                ),

                json.dumps(
                    analysis[
                        "requirements"
                    ],
                    ensure_ascii=False
                ),

                json.dumps(
                    analysis[
                        "preferred"
                    ],
                    ensure_ascii=False
                ),

                json.dumps(
                    analysis[
                        "skills"
                    ],
                    ensure_ascii=False
                ),

                AI_ANALYSIS_VERSION,

                job["id"],
            ))


            conn.commit()


            elapsed = round(
                time.monotonic()
                - start_time,
                1
            )


            success_count += 1


            print(
                f"AI 분석 완료! "
                f"({elapsed}초)"
            )


            print(
                "직무 분류:",
                analysis[
                    "job_category"
                ]
            )


            print(
                "요약:",
                analysis[
                    "summary"
                ]
            )


        except Exception as error:

            failed_count += 1


            print(
                "AI 분석 실패:"
            )


            print(
                error
            )


            # 한 공고가 실패해도
            # 다음 공고 계속 진행
            continue


    conn.close()


    print()
    print("-" * 70)


    print(
        "AI 분석 성공:",
        success_count
    )


    print(
        "AI 분석 실패:",
        failed_count
    )


    return {
        "success":
            success_count,

        "failed":
            failed_count,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("AI JOB AGENT - 자동 업데이트")
    print("=" * 70)


    # --------------------------------------------------------
    # 1. 잡코리아 수집
    # --------------------------------------------------------

    jobs = (
        collect_jobkorea()
    )


    # --------------------------------------------------------
    # 2. DB 저장
    # --------------------------------------------------------

    save_jobs_to_database(
        jobs
    )


    # --------------------------------------------------------
    # 3. Python 적합도 계산
    # --------------------------------------------------------

    recommendations = (
        recalculate_scores()
    )


    # --------------------------------------------------------
    # 4. 좋은 공고만 Qwen 자동분석
    # --------------------------------------------------------

    ai_result = (
        auto_analyze_jobs()
    )


    # --------------------------------------------------------
    # 종료
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("AI JOB AGENT 업데이트 완료")
    print("=" * 70)


    print(
        "수집 레코드:",
        len(jobs)
    )


    print(
        "추천 공고:",
        len(recommendations)
    )


    print(
        "신규 AI 분석 성공:",
        ai_result["success"]
    )


    print(
        "AI 분석 실패:",
        ai_result["failed"]
    )


    print()
    print(
        "대시보드 실행:"
    )


    print()
    print(
        "streamlit run app.py"
    )

    print()


if __name__ == "__main__":

    try:

        main()


    except KeyboardInterrupt:

        print()
        print(
            "사용자가 작업을 중단했습니다."
        )


    except Exception as error:

        print()
        print("=" * 70)
        print("업데이트 실패")
        print("=" * 70)


        print(
            type(error).__name__
        )


        print(
            error
        )