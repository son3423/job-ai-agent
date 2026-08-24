import sqlite3
import streamlit as st


# =========================================
# 1. 페이지 설정
# =========================================

st.set_page_config(
    page_title="AI 채용공고 Assistant",
    page_icon="💼",
    layout="wide"
)


st.title("💼 AI 채용공고 Assistant")

st.caption(
    "채용공고를 검색하고 AI 분석 결과를 확인할 수 있습니다."
)


# =========================================
# 2. 데이터베이스에서 공고 가져오기
# =========================================

conn = sqlite3.connect("full_jobs.db")

cursor = conn.cursor()

cursor.execute("""
SELECT
    id,
    title,
    company,
    location,
    posted,
    url,
    description,
    ai_summary
FROM jobs
""")

jobs = cursor.fetchall()

conn.close()


# =========================================
# 3. 검색 / 필터
# =========================================

st.divider()

st.subheader("🔎 공고 검색")


search_keyword = st.text_input(
    "검색어",
    placeholder="예: Python, Engineer, 자동차..."
)


companies = sorted(
    list(
        set(
            job[2]
            for job in jobs
            if job[2]
        )
    )
)


locations = sorted(
    list(
        set(
            job[3]
            for job in jobs
            if job[3]
        )
    )
)


col1, col2, col3, col4 = st.columns(4)


with col1:

    selected_company = st.selectbox(
        "회사",
        ["전체"] + companies
    )


with col2:

    selected_location = st.selectbox(
        "지역",
        ["전체"] + locations
    )


with col3:

    ai_filter = st.selectbox(
        "AI 분석 상태",
        [
            "전체",
            "분석 완료",
            "분석 전"
        ]
    )


with col4:

    sort_option = st.selectbox(
        "정렬",
        [
            "최신 공고 ID순",
            "오래된 공고 ID순",
            "직무명순"
        ]
    )


# =========================================
# 4. 필터 적용
# =========================================

filtered_jobs = []


for job in jobs:

    job_id = job[0]
    title = job[1]
    company = job[2]
    location = job[3]
    posted = job[4]
    url = job[5]
    description = job[6]
    ai_summary = job[7]


    # 검색어
    if search_keyword:

        keyword = search_keyword.lower()

        searchable_text = (
            f"{title} "
            f"{company} "
            f"{location} "
            f"{description or ''} "
            f"{ai_summary or ''}"
        ).lower()

        if keyword not in searchable_text:
            continue


    # 회사
    if selected_company != "전체":

        if company != selected_company:
            continue


    # 지역
    if selected_location != "전체":

        if location != selected_location:
            continue


    # AI 분석 상태
    if ai_filter == "분석 완료":

        if not ai_summary:
            continue


    elif ai_filter == "분석 전":

        if ai_summary:
            continue


    filtered_jobs.append(job)


# =========================================
# 5. 정렬
# =========================================

if sort_option == "최신 공고 ID순":

    filtered_jobs.sort(
        key=lambda x: x[0],
        reverse=True
    )


elif sort_option == "오래된 공고 ID순":

    filtered_jobs.sort(
        key=lambda x: x[0]
    )


elif sort_option == "직무명순":

    filtered_jobs.sort(
        key=lambda x: x[1].lower()
    )


# =========================================
# 6. 현황 표시
# =========================================

st.divider()


total_count = len(filtered_jobs)

analyzed_count = sum(
    1
    for job in filtered_jobs
    if job[7]
)


not_analyzed_count = (
    total_count - analyzed_count
)


metric1, metric2, metric3 = st.columns(3)


metric1.metric(
    "검색된 공고",
    total_count
)


metric2.metric(
    "AI 분석 완료",
    analyzed_count
)


metric3.metric(
    "AI 분석 전",
    not_analyzed_count
)


# =========================================
# 7. 공고 카드 출력
# =========================================

for job in filtered_jobs:

    job_id = job[0]
    title = job[1]
    company = job[2]
    location = job[3]
    posted = job[4]
    url = job[5]
    description = job[6]
    ai_summary = job[7]


    st.divider()


    # -----------------------------
    # 제목 + AI 상태
    # -----------------------------

    title_col, status_col = st.columns(
        [5, 1]
    )


    with title_col:

        st.subheader(title)


    with status_col:

        if ai_summary:

            st.success("AI 분석 완료")

        else:

            st.warning("분석 전")


    # -----------------------------
    # 기본 정보
    # -----------------------------

    info1, info2, info3 = st.columns(3)


    with info1:

        st.write(
            f"🏢 **{company}**"
        )


    with info2:

        st.write(
            f"📍 {location}"
        )


    with info3:

        st.write(
            f"📅 {posted}"
        )


    # -----------------------------
    # AI 분석
    # -----------------------------

    if ai_summary:

        with st.expander(
            "🤖 AI 분석 결과 보기"
        ):

            st.write(ai_summary)


    # -----------------------------
    # 원본 공고 본문
    # -----------------------------

    if description:

        with st.expander(
            "📄 수집된 원본 내용 보기"
        ):

            st.text(description)


    # -----------------------------
    # 원문 사이트 이동
    # -----------------------------

    if url:

        st.link_button(
            "🔗 원문 공고 열기",
            url
        )