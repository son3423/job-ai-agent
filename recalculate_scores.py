import sqlite3
import json
import re


DB_FILE = "jobkorea_jobs.db"


# ============================================================
# 기계공학 핵심 키워드
#
# 직무 자체가 기계공학과 직접 연결되는 표현
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
#
# 기계와 관련될 수 있지만 이것만으로
# 기계 직무라고 단정하기 어려운 표현
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
# 전기 / 전자 성격이 강한 키워드
#
# 로봇이라는 단어만 있다고
# 무조건 기계 직무로 판단하는 문제 방지
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
# 단순 정비 / 유지보수 성격 키워드
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
# 설계 / 개발 / 엔지니어링 성격 확인
#
# 유지보수라는 단어가 있어도
# 설계/개발 업무가 같이 있으면 무조건 낮추지 않음
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

    # "전기계장" 안의 "기계" 오탐 방지
    text = text.replace(
        "전기계장",
        ""
    )

    return text


# ============================================================
# 특정 키워드가 하나라도 존재하는지 확인
# ============================================================

def contains_any(
    text,
    keywords
):

    text = normalize_text(text)

    for keyword in keywords:

        if keyword.lower() in text:
            return True

    return False


# ============================================================
# 1차 기계공학 필터 점수
#
# Qwen 대상으로 보낼 공고를 찾기 위한 점수
# 최종 적합도와는 별개
# ============================================================

def calculate_filter_score(
    title,
    responsibilities,
    description,
    employment_type
):

    title = normalize_text(title)

    responsibilities = normalize_text(
        responsibilities
    )

    description = normalize_text(
        description
    )

    employment_type = normalize_text(
        employment_type
    )


    # --------------------------------------------------------
    # 교육 / 연수 제외
    # --------------------------------------------------------

    exclude_text = (
        f"{title} "
        f"{employment_type}"
    )

    for keyword in EXCLUDE_KEYWORDS:

        if keyword.lower() in exclude_text:
            return -100


    score = 0


    # --------------------------------------------------------
    # 제목
    # --------------------------------------------------------

    for keyword in CORE_MECHANICAL_KEYWORDS:

        if keyword.lower() in title:
            score += 5


    for keyword in MECHANICAL_SUPPORT_KEYWORDS:

        if keyword.lower() in title:
            score += 2


    # --------------------------------------------------------
    # 모집분야
    # --------------------------------------------------------

    for keyword in CORE_MECHANICAL_KEYWORDS:

        if keyword.lower() in responsibilities:
            score += 4


    for keyword in MECHANICAL_SUPPORT_KEYWORDS:

        if keyword.lower() in responsibilities:
            score += 1


    # --------------------------------------------------------
    # 본문은 신뢰도가 낮으므로 약하게 반영
    # --------------------------------------------------------

    for keyword in CORE_MECHANICAL_KEYWORDS:

        if keyword.lower() in description:
            score += 1


    return score


# ============================================================
# 경력직 전용 공고인지 확인
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
#
# 규칙으로 판단 가능한 것은 Qwen에게 맡기지 않음
# ============================================================

def determine_entry_fit(career):

    if not career:
        return "확인 필요"

    text = career.lower()


    # --------------------------------------------------------
    # 명확한 경력무관
    # --------------------------------------------------------

    if "경력무관" in text:
        return "지원 가능"


    # --------------------------------------------------------
    # 신입 포함
    # --------------------------------------------------------

    if "신입" in text:

        # 신입·경력(2년 이상) 같은 애매한 표현
        years = re.findall(
            r"(\d+)\s*년\s*이상",
            text
        )

        if years:
            return "확인 필요"

        return "지원 가능"


    # --------------------------------------------------------
    # 경력만 존재
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # 기계공학 핵심 표현 존재 여부
    # --------------------------------------------------------

    core_hit = contains_any(
        text,
        CORE_MECHANICAL_KEYWORDS
    )


    support_hit = contains_any(
        text,
        MECHANICAL_SUPPORT_KEYWORDS
    )


    electrical_hit = contains_any(
        text,
        ELECTRICAL_KEYWORDS
    )


    # --------------------------------------------------------
    # 전기/전자 중심 직무
    #
    # 예:
    # 로봇 전장 엔지니어
    #
    # 로봇이라는 단어가 있어도
    # 실제 업무가 전장이라면 기계 연관성 하향
    # --------------------------------------------------------

    if (
        electrical_hit
        and
        not core_hit
    ):

        if support_hit:
            return "중간"

        return "낮음"


    # --------------------------------------------------------
    # 명확한 기계 직무
    # --------------------------------------------------------

    if core_hit:
        return "높음"


    # --------------------------------------------------------
    # 설비 / 제조 / 설계 등
    # 간접적인 기계 연관성
    # --------------------------------------------------------

    if support_hit:
        return "중간"


    return "낮음"


# ============================================================
# 관심 직무 연관성
# ============================================================

def determine_interest_fit(
    title,
    responsibilities
):

    text = normalize_text(
        f"{title or ''} "
        f"{responsibilities or ''}"
    )


    # --------------------------------------------------------
    # 사용자 관심 직무와 직접 연결
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # 정비 / 단순 유지보수 직무인지 확인
    # --------------------------------------------------------

    maintenance_hit = contains_any(
        text,
        MAINTENANCE_KEYWORDS
    )


    engineering_hit = contains_any(
        text,
        ENGINEERING_KEYWORDS
    )


    # 단순 정비/유지보수 중심이면 관심도 낮음
    if (
        maintenance_hit
        and
        not engineering_hit
    ):
        return "낮음"


    # --------------------------------------------------------
    # 전장 / 전기전자 중심 직무 확인
    # --------------------------------------------------------

    electrical_hit = contains_any(
        text,
        ELECTRICAL_KEYWORDS
    )


    # 전장 직무는 로봇과 관련돼도
    # 현재 기계 중심 관심직무 기준에서는 중간
    if electrical_hit:

        direct_mechanical_interest = (
            contains_any(
                text,
                strong_interest_keywords
            )
        )

        if not direct_mechanical_interest:
            return "중간"


    # --------------------------------------------------------
    # 강한 관심직무 표현
    # --------------------------------------------------------

    for keyword in strong_interest_keywords:

        if keyword.lower() in text:
            return "높음"


    # --------------------------------------------------------
    # 일반 관련 표현
    # --------------------------------------------------------

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
# 한 공고에 여러 직무가 섞여 있는지 판단
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


    # --------------------------------------------------------
    # 부문별 / 직무별 공고
    # --------------------------------------------------------

    multi_role_words = [
        "부문별",
        "직무별",
    ]


    for word in multi_role_words:

        if word in title_text:
            return True


    # --------------------------------------------------------
    # 모집분야가 쉼표로 많이 분리된 경우
    #
    # 예:
    # Sales Engineer,
    # Motor Design Engineer,
    # Production Engineer,
    # PLC,
    # SQE ...
    # --------------------------------------------------------

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
# 고용형태 점수
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
# 최종 적합도
#
# 기본 100점
#
# 전공            35
# 신입            30
# 관심 직무       25
# 고용형태         10
#
# 복수직무 공고   -5
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


    # --------------------------------------------------------
    # 여러 직무가 한 공고에 섞인 경우
    #
    # 정확히 어떤 직무에 신입 지원 가능한지
    # 확인이 필요하므로 5점 감점
    # --------------------------------------------------------

    if multi_role:
        multi_role_penalty = 5

    else:
        multi_role_penalty = 0


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
# DB 연결
# ============================================================

conn = sqlite3.connect(
    DB_FILE
)

cursor = conn.cursor()


# ============================================================
# 세부직무 확인 컬럼 추가
# ============================================================

cursor.execute(
    "PRAGMA table_info(jobs)"
)


existing_columns = [
    row[1]
    for row
    in cursor.fetchall()
]


if (
    "ai_detail_check"
    not in existing_columns
):

    cursor.execute("""
    ALTER TABLE jobs
    ADD COLUMN ai_detail_check TEXT
    """)

    print(
        "ai_detail_check 컬럼 생성 완료"
    )


conn.commit()


# ============================================================
# DB 읽기
# ============================================================

cursor.execute("""
SELECT
    id,
    job_title,
    company_name,
    career_requirement,
    employment_type,
    responsibilities,
    job_description
FROM jobs
""")


jobs = cursor.fetchall()


results = []


# ============================================================
# 점수 재계산
# ============================================================

for job in jobs:

    (
        job_id,
        title,
        company,
        career,
        employment_type,
        responsibilities,
        description,
    ) = job


    # --------------------------------------------------------
    # 명확한 경력직 전용 제외
    # --------------------------------------------------------

    if not career_ok(
        career
    ):
        continue


    # --------------------------------------------------------
    # 기존 1차 필터
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # 각 항목 계산
    # --------------------------------------------------------

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


    if multi_role:

        detail_check = (
            "세부직무 확인 필요"
        )

    else:

        detail_check = (
            "단일직무"
        )


    final_score, breakdown = (
        calculate_final_score(
            major_fit,
            entry_fit,
            interest_fit,
            employment_type,
            description,
            multi_role,
        )
    )


    # --------------------------------------------------------
    # DB 갱신
    #
    # Qwen 요약 데이터는 건드리지 않음
    # --------------------------------------------------------

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

        "title":
            title,

        "company":
            company,

        "major_fit":
            major_fit,

        "entry_fit":
            entry_fit,

        "interest_fit":
            interest_fit,

        "detail_check":
            detail_check,

        "score":
            final_score,

        "breakdown":
            breakdown,
    })


# ============================================================
# DB 저장
# ============================================================

conn.commit()

conn.close()


# ============================================================
# 점수순 정렬
# ============================================================

results.sort(
    key=lambda x:
        x["score"],
    reverse=True
)


# ============================================================
# 출력
# ============================================================

print()
print("=" * 75)

print(
    "개선된 Python 적합도 점수 재계산 완료"
)

print("=" * 75)


print(
    "재계산 공고:",
    len(results)
)

print()


for (
    index,
    job
) in enumerate(
    results,
    start=1
):

    print("-" * 75)


    print(
        f"[{index}] "
        f"[{job['score']}점] "
        f"{job['title']}"
    )


    print(
        "회사:",
        job["company"]
    )


    print(
        "전공:",
        job["major_fit"],
        f"({job['breakdown']['major']}/35)"
    )


    print(
        "신입:",
        job["entry_fit"],
        f"({job['breakdown']['entry']}/30)"
    )


    print(
        "관심직무:",
        job["interest_fit"],
        f"({job['breakdown']['interest']}/25)"
    )


    print(
        "고용형태:",
        f"{job['breakdown']['employment']}/10"
    )


    print(
        "세부직무:",
        job["detail_check"]
    )


    penalty = (
        job["breakdown"][
            "multi_role_penalty"
        ]
    )


    if penalty != 0:

        print(
            "복수직무 감점:",
            penalty
        )


print()
print("=" * 75)

print(
    "완료"
)

print("=" * 75)