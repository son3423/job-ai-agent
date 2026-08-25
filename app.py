import sqlite3
import json

import streamlit as st
import ollama


# ============================================================
# 기본 설정
# ============================================================

DB_FILE = "jobkorea_jobs.db"
MODEL_NAME = "qwen3:4b"


st.set_page_config(
    page_title="AI Job Agent",
    page_icon="🔍",
    layout="wide",
)


# ============================================================
# DB 초기 설정
# ============================================================

def prepare_database():

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "PRAGMA table_info(jobs)"
    )

    columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    # 예전 Qwen 분석 결과와
    # 새 분석 결과를 구분하기 위한 버전 컬럼
    if "ai_analysis_version" not in columns:

        cursor.execute("""
        ALTER TABLE jobs
        ADD COLUMN ai_analysis_version TEXT
        """)

    conn.commit()
    conn.close()


# ============================================================
# JSON 배열 안전하게 읽기
# ============================================================

def parse_json_list(value):

    if not value:
        return []

    if isinstance(value, list):
        return value

    try:

        result = json.loads(value)

        if isinstance(result, list):
            return result

        return [str(result)]

    except:
        return []


# ============================================================
# 날짜 보기 좋게 변경
# ============================================================

def format_date(value):

    if not value:
        return "정보 없음"

    # 2026-09-05T00:00:00.000Z
    # →
    # 2026-09-05

    if "T" in value:
        return value.split("T")[0]

    return value


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
# 추천 공고 불러오기
#
# ai_detail_check 값이 있다는 것은
# 최신 Python 필터를 통과한 공고라는 의미
# ============================================================

def load_jobs():

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        id,
        job_title,
        company_name,
        location,
        career_requirement,
        education_requirement,
        employment_type,
        responsibilities,
        job_description,
        application_deadline,
        job_posting_url,

        ai_major_fit,
        ai_entry_level_fit,
        ai_interest_fit,
        ai_fit_score,
        ai_score_breakdown,
        ai_detail_check,

        ai_job_category,
        ai_summary,
        ai_main_tasks,
        ai_requirements,
        ai_preferred,
        ai_skills,
        ai_analysis_version

    FROM jobs

    WHERE ai_detail_check IS NOT NULL

    ORDER BY ai_fit_score DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# Qwen 결과 JSON 파싱
# ============================================================

def parse_ai_json(text):

    text = text.strip()

    # 정상 JSON
    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    # 앞뒤에 텍스트가 붙은 경우
    start = text.find("{")
    end = text.rfind("}")

    if (
        start != -1
        and end != -1
        and end > start
    ):

        return json.loads(
            text[start:end + 1]
        )

    raise ValueError(
        "AI 응답에서 JSON을 찾지 못했습니다."
    )


# ============================================================
# 리스트 형태 안전 처리
# ============================================================

def ensure_list(value):

    if isinstance(value, list):
        return value

    if value is None:
        return []

    return [str(value)]


# ============================================================
# 선택한 공고 하나만 Qwen 분석
# ============================================================

def analyze_job_with_qwen(job):

    description = clean_description(
        job["job_description"]
    )

    # 로컬 LLM 속도를 위해
    # 상세본문 길이 제한
    description_for_ai = (
        description[:1400]
    )

    prompt = f"""
아래 채용공고에서 채용 정보를 구조적으로 추출하라.

중요 규칙:

1. 공고에 실제로 존재하는 정보만 사용한다.
2. 없는 정보를 추측하지 않는다.
3. 정보가 없으면 빈 배열 []로 반환한다.
4. 지원자의 경험이나 능력을 임의로 만들지 않는다.
5. 반드시 JSON 형식으로만 답한다.

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

    response = ollama.chat(
        model=MODEL_NAME,

        messages=[
            {
                "role": "user",
                "content": prompt,
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
        response["message"]["content"]
    )

    analysis = parse_ai_json(
        ai_text
    )

    result = {

        "job_category":
            analysis.get(
                "job_category"
            )
            or "확인 필요",

        "summary":
            analysis.get(
                "summary"
            )
            or "요약 정보 없음",

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

    return result


# ============================================================
# AI 분석 결과 DB 저장
# ============================================================

def save_ai_analysis(
    job_id,
    analysis
):

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

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

        analysis["job_category"],

        analysis["summary"],

        json.dumps(
            analysis["main_tasks"],
            ensure_ascii=False
        ),

        json.dumps(
            analysis["requirements"],
            ensure_ascii=False
        ),

        json.dumps(
            analysis["preferred"],
            ensure_ascii=False
        ),

        json.dumps(
            analysis["skills"],
            ensure_ascii=False
        ),

        "fast_v1",

        job_id,
    ))

    conn.commit()
    conn.close()


# ============================================================
# DB 준비
# ============================================================

prepare_database()


# ============================================================
# 제목
# ============================================================

st.title(
    "🔍 AI Job Agent"
)

st.caption(
    "기계공학 신입 채용공고 자동 수집 · 필터링 · AI 분석"
)


# ============================================================
# 데이터 불러오기
# ============================================================

jobs = load_jobs()


if not jobs:

    st.warning(
        "현재 추천 공고가 없습니다."
    )

    st.stop()


# ============================================================
# 상단 통계
# ============================================================

scores = [
    job["ai_fit_score"] or 0
    for job in jobs
]


col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "추천 공고",
        f"{len(jobs)}개"
    )


with col2:

    st.metric(
        "최고 적합도",
        f"{max(scores)}점"
    )


with col3:

    average_score = round(
        sum(scores)
        / len(scores),
        1
    )

    st.metric(
        "평균 적합도",
        f"{average_score}점"
    )


st.divider()


# ============================================================
# 필터 영역
# ============================================================

st.subheader(
    "공고 검색 및 필터"
)


filter_col1, filter_col2 = (
    st.columns(2)
)


with filter_col1:

    search_keyword = st.text_input(
        "검색",
        placeholder="회사명 또는 직무명을 검색하세요"
    )


with filter_col2:

    min_score = st.slider(
        "최소 적합도",
        min_value=0,
        max_value=100,
        value=70,
        step=5,
    )


filter_col3, filter_col4 = (
    st.columns(2)
)


with filter_col3:

    entry_filter = st.selectbox(
        "신입 지원 조건",
        [
            "전체",
            "지원 가능",
            "확인 필요",
            "지원 어려움",
        ]
    )


with filter_col4:

    role_filter = st.selectbox(
        "세부직무 상태",
        [
            "전체",
            "단일직무",
            "세부직무 확인 필요",
        ]
    )


# ============================================================
# 화면용 필터 적용
# ============================================================

filtered_jobs = []


for job in jobs:

    score = (
        job["ai_fit_score"]
        or 0
    )


    # 점수
    if score < min_score:
        continue


    # 검색
    if search_keyword:

        search_text = (
            f"{job['job_title']} "
            f"{job['company_name']}"
        ).lower()

        if (
            search_keyword.lower()
            not in search_text
        ):
            continue


    # 신입 조건
    if (
        entry_filter != "전체"
        and
        job["ai_entry_level_fit"]
        != entry_filter
    ):
        continue


    # 세부직무
    if (
        role_filter != "전체"
        and
        job["ai_detail_check"]
        != role_filter
    ):
        continue


    filtered_jobs.append(job)


st.write(
    f"**{len(filtered_jobs)}개 공고가 검색되었습니다.**"
)

st.divider()


# ============================================================
# 공고 출력
# ============================================================

for job in filtered_jobs:

    score = (
        job["ai_fit_score"]
        or 0
    )


    # --------------------------------------------------------
    # 점수별 아이콘
    # --------------------------------------------------------

    if score >= 90:
        score_icon = "🔥"

    elif score >= 80:
        score_icon = "✅"

    elif score >= 70:
        score_icon = "🔎"

    else:
        score_icon = "⚪"


    expander_title = (
        f"{score_icon} "
        f"{score}점 | "
        f"{job['job_title']} "
        f"- {job['company_name']}"
    )


    with st.expander(
        expander_title
    ):

        # ====================================================
        # 기본 평가
        # ====================================================

        c1, c2, c3, c4 = (
            st.columns(4)
        )


        with c1:

            st.metric(
                "적합도",
                f"{score}점"
            )


        with c2:

            st.write(
                "**전공 연관성**"
            )

            st.write(
                job["ai_major_fit"]
                or "정보 없음"
            )


        with c3:

            st.write(
                "**신입 지원**"
            )

            st.write(
                job["ai_entry_level_fit"]
                or "정보 없음"
            )


        with c4:

            st.write(
                "**관심직무**"
            )

            st.write(
                job["ai_interest_fit"]
                or "정보 없음"
            )


        # ====================================================
        # 세부 직무 경고
        # ====================================================

        if (
            job["ai_detail_check"]
            ==
            "세부직무 확인 필요"
        ):

            st.warning(
                "여러 직무가 함께 포함된 공고입니다. "
                "지원하려는 세부직무의 자격요건을 "
                "원문에서 확인해야 합니다."
            )


        st.divider()


        # ====================================================
        # 기본 채용정보
        # ====================================================

        st.subheader(
            "채용 정보"
        )


        st.write(
            "**회사:**",
            job["company_name"]
        )


        st.write(
            "**경력:**",
            job["career_requirement"]
            or "정보 없음"
        )


        st.write(
            "**학력:**",
            job["education_requirement"]
            or "정보 없음"
        )


        st.write(
            "**고용형태:**",
            job["employment_type"]
            or "정보 없음"
        )


        st.write(
            "**마감일:**",
            format_date(
                job[
                    "application_deadline"
                ]
            )
        )


        st.write(
            "**근무지:**",
            job["location"]
            or "정보 없음"
        )


        if job["responsibilities"]:

            st.write(
                "**모집분야:**",
                job["responsibilities"]
            )


        # ====================================================
        # 잡코리아 원문 버튼
        # ====================================================

        if job["job_posting_url"]:

            st.link_button(
                "🔗 잡코리아 원문 보기",
                job["job_posting_url"]
            )


        st.divider()


        # ====================================================
        # AI 상세 분석
        # ====================================================

        st.subheader(
            "🤖 AI 상세 분석"
        )


        # ----------------------------------------------------
        # 새 방식으로 분석된 결과가 있는 경우만 표시
        # ----------------------------------------------------

        if (
            job["ai_analysis_version"]
            == "fast_v1"
        ):

            st.success(
                "AI 분석 완료"
            )


            st.write(
                "**직무 분류:**",
                job["ai_job_category"]
                or "정보 없음"
            )


            st.write(
                "**한 줄 요약:**",
                job["ai_summary"]
                or "정보 없음"
            )


            main_tasks = parse_json_list(
                job["ai_main_tasks"]
            )

            requirements = parse_json_list(
                job["ai_requirements"]
            )

            preferred = parse_json_list(
                job["ai_preferred"]
            )

            skills = parse_json_list(
                job["ai_skills"]
            )


            st.write(
                "**주요 업무**"
            )

            if main_tasks:

                for item in main_tasks:
                    st.write(
                        f"- {item}"
                    )

            else:

                st.write(
                    "공고에서 구체적인 업무를 확인하기 어렵습니다."
                )


            st.write(
                "**지원 자격**"
            )

            if requirements:

                for item in requirements:
                    st.write(
                        f"- {item}"
                    )

            else:

                st.write(
                    "별도 정보 없음"
                )


            st.write(
                "**우대 사항**"
            )

            if preferred:

                for item in preferred:
                    st.write(
                        f"- {item}"
                    )

            else:

                st.write(
                    "별도 정보 없음"
                )


            st.write(
                "**기술 키워드**"
            )

            if skills:

                st.write(
                    " · ".join(
                        skills
                    )
                )

            else:

                st.write(
                    "별도 정보 없음"
                )


        else:

            st.info(
                "아직 이 공고는 Qwen 상세 분석을 하지 않았습니다."
            )


        # ====================================================
        # AI 실행 버튼
        # ====================================================

        button_text = (
            "🔄 AI 다시 분석"
            if
            job["ai_analysis_version"]
            == "fast_v1"

            else

            "🤖 AI 상세 분석 실행"
        )


        if st.button(
            button_text,
            key=f"ai_{job['id']}"
        ):

            with st.spinner(
                "Qwen이 이 공고 하나만 분석하고 있습니다..."
            ):

                try:

                    analysis = (
                        analyze_job_with_qwen(
                            job
                        )
                    )


                    save_ai_analysis(
                        job["id"],
                        analysis
                    )


                    st.success(
                        "AI 분석이 완료되었습니다."
                    )


                    st.rerun()


                except Exception as error:

                    st.error(
                        f"AI 분석 실패: {error}"
                    )


        # ====================================================
        # 원문 상세내용
        # ====================================================

        with st.expander(
            "📄 수집된 상세내용 보기"
        ):

            st.write(
                clean_description(
                    job["job_description"]
                )
            )