import sqlite3


DB_FILE = "jobkorea_jobs.db"


# ==========================================
# 강한 기계공학 관련 키워드
# ==========================================

STRONG_KEYWORDS = [
    "기계",
    "기구",
    "기계설계",
    "기구설계",
    "생산기술",
    "공정개발",
    "공정기술",
    "자동화",
    "로봇",
    "모터",
    "열관리",
    "냉동",
    "공조",
    "hvac",
    "배터리",
    "설비기술",
    "장비설계",
    "구조설계",
    "구조해석",
    "cae",
    "cad",
    "catia",
    "solidworks",
    "mechanical",
    "production engineer",
    "design engineer",
    "manufacturing engineer",
]


# ==========================================
# 보조 키워드
# 이것만 하나 있다고 바로 통과시키지는 않음
# ==========================================

WEAK_KEYWORDS = [
    "설계",
    "공정",
    "제조",
    "품질",
    "설비",
    "장비",
    "해석",
    "자동차",
    "유지보수",
]


# ==========================================
# 제외할 공고
# ==========================================

EXCLUDE_KEYWORDS = [
    "취업캠프",
    "교육생",
    "연수생",
    "국비지원",
    "교육과정",
]


# ==========================================
# 경력 조건 확인
# ==========================================

def career_ok(career):
    if not career:
        return True

    text = career.lower()

    # 신입 지원 가능
    if "신입" in text:
        return True

    # 경력무관
    if "경력무관" in text:
        return True

    # 명확한 경력직만 있는 경우 제외
    if "경력" in text:
        return False

    return True


# ==========================================
# 직무 관련성 점수 계산
# ==========================================

def calculate_score(
    title,
    responsibilities,
    description,
    employment_type
):
    title = (title or "").lower()
    responsibilities = (responsibilities or "").lower()
    description = (description or "").lower()
    employment_type = (employment_type or "").lower()

    # --------------------------------------
    # "전기계장" 속의 "기계"가
    # 잘못 매칭되는 현상 방지
    # --------------------------------------

    title = title.replace("전기계장", "")
    responsibilities = responsibilities.replace("전기계장", "")
    description = description.replace("전기계장", "")

    # --------------------------------------
    # 교육 / 연수 공고 제외
    # --------------------------------------

    exclude_text = f"{title} {employment_type}"

    for keyword in EXCLUDE_KEYWORDS:
        if keyword.lower() in exclude_text:
            return -100, []

    score = 0
    matched = []

    # --------------------------------------
    # 제목
    # 가장 신뢰도가 높음
    # --------------------------------------

    for keyword in STRONG_KEYWORDS:
        if keyword.lower() in title:
            score += 5
            matched.append(f"제목:{keyword}")

    for keyword in WEAK_KEYWORDS:
        if keyword.lower() in title:
            score += 2
            matched.append(f"제목:{keyword}")

    # --------------------------------------
    # 모집분야 / responsibilities
    # 두 번째로 신뢰도가 높음
    # --------------------------------------

    for keyword in STRONG_KEYWORDS:
        if keyword.lower() in responsibilities:
            score += 4
            matched.append(f"업무:{keyword}")

    for keyword in WEAK_KEYWORDS:
        if keyword.lower() in responsibilities:
            score += 1
            matched.append(f"업무:{keyword}")

    # --------------------------------------
    # 상세본문
    # 잡코리아 잡음이 있으므로
    # 강한 키워드만 약하게 반영
    # --------------------------------------

    for keyword in STRONG_KEYWORDS:
        if keyword.lower() in description:
            score += 1
            matched.append(f"본문:{keyword}")

    # 중복 근거 제거
    matched = list(dict.fromkeys(matched))

    return score, matched


# ==========================================
# DB 읽기
# ==========================================

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

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
    application_deadline
FROM jobs
ORDER BY id DESC
""")

jobs = cursor.fetchall()

conn.close()


# ==========================================
# 필터링
# ==========================================

candidates = []


for job in jobs:

    (
        job_id,
        title,
        company,
        career,
        education,
        employment_type,
        responsibilities,
        description,
        deadline,
    ) = job

    # --------------------------------------
    # 경력 조건 확인
    # --------------------------------------

    if not career_ok(career):
        continue

    # --------------------------------------
    # 기계공학 관련성 점수 계산
    # --------------------------------------

    score, matched = calculate_score(
        title,
        responsibilities,
        description,
        employment_type,
    )

    # --------------------------------------
    # 4점 미만 제외
    # --------------------------------------

    if score < 4:
        continue

    candidates.append({
        "id": job_id,
        "title": title,
        "company": company,
        "career": career,
        "education": education,
        "employment_type": employment_type,
        "deadline": deadline,
        "score": score,
        "keywords": matched,
    })


# ==========================================
# 점수 높은 순으로 정렬
# ==========================================

candidates.sort(
    key=lambda x: x["score"],
    reverse=True
)


# ==========================================
# 결과 출력
# ==========================================

print("=" * 70)
print("잡코리아 기계공학 관련 공고 1차 필터")
print("=" * 70)

print("전체 DB 공고:", len(jobs))
print("필터 통과:", len(candidates))
print()


for index, job in enumerate(candidates, start=1):

    print("-" * 70)

    print(
        f"[{index}] [점수 {job['score']}] "
        f"{job['title']}"
    )

    print(
        "회사:",
        job["company"]
    )

    print(
        "경력:",
        job["career"]
    )

    print(
        "학력:",
        job["education"]
    )

    print(
        "고용형태:",
        job["employment_type"]
    )

    print(
        "마감:",
        job["deadline"]
    )

    print(
        "근거:",
        ", ".join(job["keywords"])
    )


print()
print("=" * 70)
print("필터링 완료")
print("=" * 70)