import json

import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# ------------------------------------------------
# Configuration
# ------------------------------------------------

RESULTS_URL = "https://raw.githubusercontent.com/DaZeroZs/DashboardForGame/main/challenge_leaderboard.json"
REFRESH_INTERVAL_MS = 10_000  # 10 seconds


# ------------------------------------------------
# Page setup
# ------------------------------------------------

st.set_page_config(
    page_title="Security Competition Dashboard",
    page_icon="📊",
    layout="wide",
)

refresh_count = st_autorefresh(interval=REFRESH_INTERVAL_MS, key="dashboard_refresh")

st.title("Security Competition Dashboard")
st.caption(f"Auto-refresh every 10 seconds • Refresh count: {refresh_count}")
#st.caption(f"Reading results from: {RESULTS_URL}")


# ------------------------------------------------
# Data loading
# ------------------------------------------------

@st.cache_data(ttl=5)
def load_results():
    rows = []

    try:
        response = requests.get(RESULTS_URL, timeout=20)
        response.raise_for_status()
    except requests.RequestException as e:
        st.error(f"Failed to load results from GitHub: {e}")
        return pd.DataFrame(), pd.DataFrame()

    for line_no, line in enumerate(response.text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        try:
            record = json.loads(line)
            rows.append(record)
        except json.JSONDecodeError:
            st.warning(f"Skipping invalid JSON on line {line_no}")

    if not rows:
        return pd.DataFrame(), pd.DataFrame()

    df = pd.DataFrame(rows)

    for col in ["timestamp", "submitted_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    challenge_rows = []
    for _, row in df.iterrows():
        solved = row.get("solved_challenges", []) or []
        for challenge in solved:
            challenge_rows.append(
                {
                    "student": row.get("student"),
                    "execution_id": row.get("execution_id"),
                    "submitted_at": row.get("submitted_at"),
                    "challenge_name": challenge.get("name"),
                    "difficulty": challenge.get("difficulty"),
                    "points": challenge.get("points"),
                    "score": row.get("score"),
                    "solved_count": row.get("solved_count"),
                    "prompt": row.get("prompt"),
                }
            )

    challenges_df = pd.DataFrame(challenge_rows)

    return df, challenges_df


df, challenges_df = load_results()

if df.empty:
    st.warning("No results found yet.")
    st.stop()


# ------------------------------------------------
# Transformations
# ------------------------------------------------

sort_col = "submitted_at" if "submitted_at" in df.columns else "timestamp"

latest_df = (
    df.sort_values(sort_col)
    .groupby("student", as_index=False)
    .tail(1)
    .sort_values(["score", "solved_count", sort_col], ascending=[False, False, True])
    .reset_index(drop=True)
)

latest_df.index = latest_df.index + 1
latest_df["rank"] = latest_df.index

leaderboard = latest_df[
    ["rank", "student", "score", "solved_count", "execution_id", sort_col]
].copy().rename(columns={sort_col: "last_submission"})

latest_submission = df.sort_values(sort_col, ascending=False).iloc[0]

history_cols = [
    c for c in ["student", "score", "solved_count", "execution_id", "submitted_at", "prompt"]
    if c in df.columns
]
history_df = df[history_cols].sort_values(sort_col, ascending=False).copy()

if not challenges_df.empty:
    freq_df = (
        challenges_df.groupby("challenge_name")
        .size()
        .reset_index(name="times_solved")
        .sort_values(["times_solved", "challenge_name"], ascending=[False, True])
    )

    points_df = (
        challenges_df.groupby("challenge_name", as_index=False)["points"]
        .max()
        .sort_values(["points", "challenge_name"], ascending=[False, True])
        .set_index("challenge_name")
    )

    difficulty_df = (
        challenges_df.groupby("challenge_name", as_index=False)["difficulty"]
        .max()
        .sort_values(["difficulty", "challenge_name"], ascending=[False, True])
    )
else:
    freq_df = pd.DataFrame()
    points_df = pd.DataFrame()
    difficulty_df = pd.DataFrame()


# ------------------------------------------------
# Top metrics
# ------------------------------------------------

m1, m2, m3, m4 = st.columns(4)
m1.metric("Participants", int(latest_df["student"].nunique()))
m2.metric("Top Score", int(latest_df["score"].max()))
m3.metric("Total Submissions", int(len(df)))
m4.metric(
    "Unique Challenges Solved",
    int(challenges_df["challenge_name"].nunique()) if not challenges_df.empty else 0,
)

st.divider()


# ------------------------------------------------
# Leaderboard + latest submission
# ------------------------------------------------

left, right = st.columns([2, 1])

with left:
    st.subheader("Leaderboard")
    st.dataframe(leaderboard, use_container_width=True, hide_index=True)

with right:
    st.subheader("Latest Submission")
    st.write(f"**Student:** {latest_submission['student']}")
    st.write(f"**Score:** {latest_submission['score']}")
    st.write(f"**Solved:** {latest_submission['solved_count']}")
    st.write(f"**Execution ID:** {latest_submission['execution_id']}")
    st.write(f"**Prompt:** {latest_submission.get('prompt', '')}")

st.divider()


# ------------------------------------------------
# Charts
# ------------------------------------------------

c1, c2 = st.columns(2)

with c1:
    st.subheader("Score by Student")
    score_chart_df = (
        latest_df.sort_values("score", ascending=False)[["student", "score"]]
        .set_index("student")
    )
    st.bar_chart(score_chart_df)

with c2:
    st.subheader("Solved Challenges by Student")
    solved_chart_df = (
        latest_df.sort_values("solved_count", ascending=False)[["student", "solved_count"]]
        .set_index("student")
    )
    st.bar_chart(solved_chart_df)

st.divider()


# ------------------------------------------------
# Submission history
# ------------------------------------------------

st.subheader("Submission History")
st.dataframe(history_df, use_container_width=True, hide_index=True)


# ------------------------------------------------
# Challenge analytics
# ------------------------------------------------

if not challenges_df.empty:
    st.divider()

    a1, a2 = st.columns(2)

    with a1:
        st.subheader("Most Frequently Solved Challenges")
        st.dataframe(freq_df, use_container_width=True, hide_index=True)

    with a2:
        st.subheader("Points by Challenge")
        st.bar_chart(points_df)

    b1, b2 = st.columns(2)

    with b1:
        st.subheader("Challenge Difficulty")
        st.dataframe(difficulty_df, use_container_width=True, hide_index=True)

    with b2:
        st.subheader("Challenge Detail")
        challenge_detail_df = challenges_df.sort_values(
            "submitted_at", ascending=False
        ).copy()
        st.dataframe(challenge_detail_df, use_container_width=True, hide_index=True)