import sqlite3
import json
import re
import ollama


DB_FILE = "jobkorea_jobs.db"

# 우선 1개만 테스트
ANALYZE_LIMIT = 1

# True:
# 기존 AI 분석 결과가 있어도 다시 Qwen 분석
#
# False:
# 이미 AI 분석된 공고는 다시 분석하지 않음
FORCE_REANALYZE = True


# ============================================================
# 기계공학 관련 강한 키워드
# ============================================================

MECHANICAL_STRONG = [
    "기계",
    "기구",
    "기계설계",
    "기구설계",
    "생산기술",
    "공정기술",
    "공정개발",
    "자동화",
    "로봇",
    "모터",
    "열관리",
    "냉동",
    "공조",
    "hvac",
    "배터리",
    "장비설계",
    "설비기술",
    "구조설계",
    "구조해석",
    "cae",
    "cad",
    "catia",
    "solidworks",
    "mechanical",
    "production engineer",
    "design engineer",
    "design engineering",
    "mechanical design",
    "manufacturing engineer",
]


# ============================================================
# 기계공학 관련 보조 키워드
# ============================================================

MECHANICAL_WEAK = [
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


# ============================================================
# 제외할 공고
# ============================================================

EXCLUDE_KEYWORDS = [
    "취업캠프",
    "교육생",
    "연수생",
    "국비지원",
    "교육과정",
]


# ============================================================
# 텍스트 정리
# ============================================================

def clean_text(text):

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

    text = " ".join(
        text.split()
    )

    return text


# ============================================================
# "전기계장" 속의 "기계" 오탐 방지
# ============================================================

def remove_false_matches(text):

    if not text:
        return ""

    return (
        text
        .lower()
        .replace(
            "전기계장",
            ""
        )
    )


# ============================================================
# Python 1차 필터 점수
#
# Qwen에게 보낼 공고를 고르는 용도
# 최종 적합도 점수가 아님
# ============================================================

def calculate_filter_score(
    title,
    responsibilities,
    description,
    employment_type
):

    title = remove_false_matches(
        title
    )

    responsibilities = remove_false_matches(
        responsibilities
    )

    description = remove_false_matches(
        description
    )

    employment_type = (
        employment_type or ""
    ).lower()


    # --------------------------------------------------------
    # 교육 / 연수 공고 제외
    # --------------------------------------------------------

    exclude_text = (
        f"{title} {employment_type}"
    )

    for keyword in EXCLUDE_KEYWORDS:

        if keyword.lower() in exclude_text:
            return -100


    score = 0


    # --------------------------------------------------------
    # 제목
    # --------------------------------------------------------

    for keyword in MECHANICAL_STRONG:

        if keyword.lower() in title:
            score += 5


    for keyword in MECHANICAL_WEAK:

        if keyword.lower() in title:
            score += 2


    # --------------------------------------------------------
    # 모집 분야
    # --------------------------------------------------------

    for keyword in MECHANICAL_STRONG:

        if keyword.lower() in responsibilities:
            score += 4


    for keyword in MECHANICAL_WEAK:

        if keyword.lower() in responsibilities:
            score += 1


    # --------------------------------------------------------
    # 상세 본문
    #
    # 잡코리아 잡음이 있으므로
    # 강한 키워드만 낮은 가중치 적용
    # --------------------------------------------------------

    for keyword in MECHANICAL_STRONG:

        if keyword.lower() in description:
            score += 1


    return score


# ============================================================
# 신입 지원 가능성
#
# AI가 아니라 Python이 직접 판단
# ============================================================

def determine_entry_fit(career):

    if not career:
        return "확인 필요"

    text = career.lower()


    # --------------------------------------------------------
    # 경력무관
    # --------------------------------------------------------

    if "경력무관" in text:
        return "지원 가능"


    # --------------------------------------------------------
    # 신입 포함
    # --------------------------------------------------------

    if "신입" in text:

        # 예:
        # 신입·경력 (2년이상)
        # 신입·경력 (3년 이상)
        #
        # 경력 연수가 신입에게도 적용되는지
        # 불분명하므로 확인 필요
        years = re.findall(
            r"(\d+)\s*년\s*이상",
            text
        )

        if years:
            return "확인 필요"

        return "지원 가능"


    # --------------------------------------------------------
    # 신입 없이 경력만 존재
    # --------------------------------------------------------

    if "경력" in text:
        return "지원 어려움"


    return "확인 필요"


# ============================================================
# 기계공학 전공 연관성
#
# 제목 + 모집분야 중심
# ============================================================

def determine_major_fit(
    title,
    responsibilities
):

    title = remove_false_matches(
        title
    )

    responsibilities = remove_false_matches(
        responsibilities
    )


    strong_hits = 0
    weak_hits = 0


    # --------------------------------------------------------
    # 강한 키워드
    # --------------------------------------------------------

    for keyword in MECHANICAL_STRONG:

        keyword = keyword.lower()

        # 제목은 더 중요하므로 2점
        if keyword in title:
            strong_hits += 2

        # 모집분야는 1점
        if keyword in responsibilities:
            strong_hits += 1


    # --------------------------------------------------------
    # 보조 키워드
    # --------------------------------------------------------

    for keyword in MECHANICAL_WEAK:

        keyword = keyword.lower()

        if keyword in title:
            weak_hits += 1

        if keyword in responsibilities:
            weak_hits += 1


    # --------------------------------------------------------
    # 판정
    # --------------------------------------------------------

    if strong_hits >= 2:
        return "높음"

    if strong_hits >= 1:
        return "중간"

    if weak_hits >= 2:
        return "중간"

    return "낮음"


# ============================================================
# 관심 직무 연관성
#
# 이번에 수정한 핵심 부분
# ============================================================

def determine_interest_fit(
    title,
    responsibilities
):

    text = (
        f"{title or ''} "
        f"{responsibilities or ''}"
    ).lower()


    # --------------------------------------------------------
    # 사용자 관심직무와 직접 연결되는 강한 표현
    #
    # 하나만 있어도 "높음"
    # --------------------------------------------------------

    strong_interest_keywords = [
        "기계설계",
        "기구설계",
        "생산기술",
        "제조기술",
        "공정기술",
        "공정개발",
        "열관리",
        "냉동",
        "공조",
        "hvac",
        "배터리",
        "자동화",

        # 영어 직무명
        "design engineer",
        "design engineering",
        "mechanical design",
        "production engineer",
        "manufacturing engineer",
    ]


    # --------------------------------------------------------
    # 관련은 있지만 범위가 넓은 표현
    # --------------------------------------------------------

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
    # 강한 키워드 확인
    # --------------------------------------------------------

    for keyword in strong_interest_keywords:

        if keyword.lower() in text:
            return "높음"


    # --------------------------------------------------------
    # 일반 키워드 개수
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


    # --------------------------------------------------------
    # 정규직
    # --------------------------------------------------------

    if "정규직" in employment:
        return 10


    # --------------------------------------------------------
    # 정규직 전환 가능한 인턴
    # --------------------------------------------------------

    if (
        "인턴" in employment
        and
        "정규직 전환 가능" in description
    ):
        return 7


    # --------------------------------------------------------
    # 일반 인턴
    # --------------------------------------------------------

    if "인턴" in employment:
        return 5


    # --------------------------------------------------------
    # 계약직
    # --------------------------------------------------------

    if "계약직" in employment:
        return 4


    return 3


# ============================================================
# 최종 적합도 계산
#
# 총 100점
#
# 전공 연관성        35점
# 신입 지원 가능성   30점
# 관심 직무 연관성   25점
# 고용 형태          10점
# ============================================================

def calculate_final_score(
    major_fit,
    entry_fit,
    interest_fit,
    employment_type,
    description
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


    total = (
        major_score
        + entry_score
        + interest_score
        + employment_score
    )


    breakdown = {
        "major": major_score,
        "entry": entry_score,
        "interest": interest_score,
        "employment": employment_score,
    }


    return total, breakdown


# ============================================================
# AI JSON 파싱
# ============================================================

def parse_ai_json(text):

    text = text.strip()


    # --------------------------------------------------------
    # 정상 JSON
    # --------------------------------------------------------

    try:

        return json.loads(
            text
        )

    except json.JSONDecodeError:
        pass


    # --------------------------------------------------------
    # JSON 앞뒤에 텍스트가 붙은 경우
    # --------------------------------------------------------

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
        "AI 응답에서 JSON을 찾을 수 없습니다."
    )


# ============================================================
# AI 리스트 값 안전 처리
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
# DB 연결
# ============================================================

conn = sqlite3.connect(
    DB_FILE
)

cursor = conn.cursor()


# ============================================================
# 필요한 AI 컬럼 생성
# ============================================================

cursor.execute(
    "PRAGMA table_info(jobs)"
)


existing_columns = [
    row[1]
    for row in cursor.fetchall()
]


required_columns = {

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

        print(
            f"{column_name} 컬럼 생성 완료"
        )


conn.commit()


# ============================================================
# DB 공고 읽기
# ============================================================

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
    application_deadline,
    ai_summary
FROM jobs
""")


rows = cursor.fetchall()


# ============================================================
# Python 1차 필터
# ============================================================

candidates = []


for row in rows:

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
        existing_ai_summary,
    ) = row


    # --------------------------------------------------------
    # 이미 AI 분석된 공고 처리
    # --------------------------------------------------------

    if (
        not FORCE_REANALYZE
        and existing_ai_summary
    ):
        continue


    # --------------------------------------------------------
    # Python 1차 필터
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
    # 전공 연관성
    # --------------------------------------------------------

    major_fit = (
        determine_major_fit(
            title,
            responsibilities
        )
    )


    # --------------------------------------------------------
    # 신입 지원 가능성
    # --------------------------------------------------------

    entry_fit = (
        determine_entry_fit(
            career
        )
    )


    # --------------------------------------------------------
    # 관심직무 연관성
    # --------------------------------------------------------

    interest_fit = (
        determine_interest_fit(
            title,
            responsibilities
        )
    )


    # --------------------------------------------------------
    # 상세본문 정리
    # --------------------------------------------------------

    cleaned_description = (
        clean_text(
            description
        )
    )


    # --------------------------------------------------------
    # Python 최종 점수
    # --------------------------------------------------------

    final_score, breakdown = (
        calculate_final_score(
            major_fit,
            entry_fit,
            interest_fit,
            employment_type,
            cleaned_description,
        )
    )


    candidates.append({

        "id":
            job_id,

        "title":
            title,

        "company":
            company,

        "career":
            career,

        "education":
            education,

        "employment_type":
            employment_type,

        "responsibilities":
            responsibilities,

        "description":
            cleaned_description,

        "deadline":
            deadline,

        "filter_score":
            filter_score,

        "major_fit":
            major_fit,

        "entry_fit":
            entry_fit,

        "interest_fit":
            interest_fit,

        "final_score":
            final_score,

        "breakdown":
            breakdown,
    })


# ============================================================
# Python 필터 점수 높은 순
# ============================================================

candidates.sort(
    key=lambda x:
        x["filter_score"],
    reverse=True
)


# ============================================================
# 테스트 분석 개수 제한
# ============================================================

candidates = (
    candidates[
        :ANALYZE_LIMIT
    ]
)


# ============================================================
# 분석 시작
# ============================================================

print()
print("=" * 70)
print("빠른 Qwen 채용공고 분석")
print("=" * 70)

print(
    "이번에 분석할 공고:",
    len(candidates)
)


# ============================================================
# Qwen 분석
# ============================================================

for (
    index,
    job
) in enumerate(
    candidates,
    start=1
):

    print()
    print("=" * 70)

    print(
        f"[{index}/"
        f"{len(candidates)}]"
    )


    print(
        "직무:",
        job["title"]
    )


    print(
        "회사:",
        job["company"]
    )


    # --------------------------------------------------------
    # Python 판단 결과
    # --------------------------------------------------------

    print()
    print(
        "[Python 판단]"
    )


    print(
        "전공 연관성:",
        job["major_fit"]
    )


    print(
        "신입 지원:",
        job["entry_fit"]
    )


    print(
        "관심직무 연관성:",
        job["interest_fit"]
    )


    print(
        "최종 적합도:",
        job["final_score"],
        "/ 100"
    )


    print()
    print(
        "Qwen 정보 추출 중..."
    )


    # --------------------------------------------------------
    # Qwen에 전달할 본문 길이 제한
    # --------------------------------------------------------

    description_for_ai = (
        job["description"][
            :1400
        ]
    )


    # --------------------------------------------------------
    # 간소화된 프롬프트
    # --------------------------------------------------------

    prompt = f"""
아래 채용공고에서 채용 정보를 구조적으로 추출하라.

중요 규칙:

1. 공고에 실제로 존재하는 정보만 사용한다.
2. 없는 정보를 추측해서 만들지 않는다.
3. 정보가 없으면 빈 배열 []로 반환한다.
4. 지원자의 경험이나 능력을 추측하지 않는다.
5. 반드시 JSON만 반환한다.

직무명:
{job["title"]}

경력:
{job["career"]}

학력:
{job["education"]}

모집분야:
{job["responsibilities"]}

상세내용:
{description_for_ai}


다음 형식으로 반환한다.

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


    try:

        # ====================================================
        # Qwen 호출
        #
        # think=False:
        # Qwen3의 긴 추론 과정을 끄고
        # 정보 추출에 집중
        # ====================================================

        response = ollama.chat(

            model="qwen3:4b",

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
                "temperature": 0,
                "num_predict": 300,
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


        # ====================================================
        # Qwen 결과 정리
        # ====================================================

        job_category = (
            analysis.get(
                "job_category"
            )
            or
            "확인 필요"
        )


        summary = (
            analysis.get(
                "summary"
            )
            or
            "요약 정보 없음"
        )


        main_tasks = (
            ensure_list(
                analysis.get(
                    "main_tasks"
                )
            )
        )


        requirements = (
            ensure_list(
                analysis.get(
                    "requirements"
                )
            )
        )


        preferred = (
            ensure_list(
                analysis.get(
                    "preferred"
                )
            )
        )


        skills = (
            ensure_list(
                analysis.get(
                    "skills"
                )
            )
        )


        # ====================================================
        # DB 저장
        # ====================================================

        cursor.execute("""
        UPDATE jobs

        SET
            ai_job_category = ?,
            ai_major_fit = ?,
            ai_entry_level_fit = ?,
            ai_interest_fit = ?,
            ai_fit_score = ?,
            ai_score_breakdown = ?,
            ai_summary = ?,
            ai_main_tasks = ?,
            ai_requirements = ?,
            ai_preferred = ?,
            ai_skills = ?

        WHERE id = ?
        """, (

            job_category,

            job["major_fit"],

            job["entry_fit"],

            job["interest_fit"],

            job["final_score"],

            json.dumps(
                job["breakdown"],
                ensure_ascii=False
            ),

            summary,

            json.dumps(
                main_tasks,
                ensure_ascii=False
            ),

            json.dumps(
                requirements,
                ensure_ascii=False
            ),

            json.dumps(
                preferred,
                ensure_ascii=False
            ),

            json.dumps(
                skills,
                ensure_ascii=False
            ),

            job["id"],
        ))


        conn.commit()


        # ====================================================
        # 결과 출력
        # ====================================================

        print()
        print(
            "Qwen 추출 완료!"
        )


        print(
            "직무 분류:",
            job_category
        )


        print(
            "요약:",
            summary
        )


        print(
            "주요 업무:",
            main_tasks
        )


        print(
            "지원 자격:",
            requirements
        )


        print(
            "우대 사항:",
            preferred
        )


        print(
            "기술 키워드:",
            skills
        )


        # ----------------------------------------------------
        # 최종 Python 점수
        # ----------------------------------------------------

        print()
        print(
            "[최종 판단]"
        )


        breakdown = (
            job["breakdown"]
        )


        print(
            "전공:",
            breakdown["major"],
            "/ 35"
        )


        print(
            "신입:",
            breakdown["entry"],
            "/ 30"
        )


        print(
            "관심직무:",
            breakdown["interest"],
            "/ 25"
        )


        print(
            "고용형태:",
            breakdown["employment"],
            "/ 10"
        )


        print(
            "최종 적합도:",
            job["final_score"],
            "/ 100"
        )


    except Exception as error:

        print()
        print(
            "Qwen 분석 실패:"
        )

        print(
            error
        )


# ============================================================
# 종료
# ============================================================

conn.close()


print()
print("=" * 70)
print("분석 완료")
print("=" * 70)