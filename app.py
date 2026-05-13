from collections import Counter

import streamlit as st

from lib.neo4j_client import get_database_name, test_connection
from lib.recommender import (
    add_interest,
    clear_user_graph,
    get_graph_summary,
    get_recommendations,
    seed_demo_graph,
)
from lib.tagger import extract_tags


MEDIA_TYPES = [
    "book",
    "manga",
    "graphic_novel",
    "movie",
    "tv_show",
    "kdrama",
    "anime",
    "music",
]


def format_media_type(value: str) -> str:
    return value.replace("_", " ").title()


def join_optional_notes(*parts: str) -> str:
    return ", ".join(part.strip() for part in parts if part and part.strip())


def render_tag_block(title: str, values: list[str]) -> None:
    st.markdown(f"**{title}**")
    st.write(", ".join(values) if values else "None yet")


def render_tag_chips(values: list[str]) -> None:
    if not values:
        st.write("None yet")
        return
    st.markdown(" ".join(f"`{value}`" for value in values))


def build_recommendation_summary(recommendations: list[dict]) -> tuple[list[tuple[str, int]], str]:
    reason_counts = Counter(
        reason
        for recommendation in recommendations
        for reason in recommendation.get("reasons", [])
    )
    top_reasons = reason_counts.most_common(3)
    if not top_reasons:
        return top_reasons, "Add more interests to generate explanation signals."

    summary = ", ".join(reason for reason, _ in top_reasons)
    return top_reasons, f"Your strongest cross-media signals are {summary}."


st.set_page_config(page_title="TasteGraph", page_icon="Graph", layout="wide")

st.session_state.setdefault("last_tags", None)
st.session_state.setdefault("last_title", "")

st.title("TasteGraph")
st.write(
    "TasteGraph maps what you love across books, shows, manga, films, and music "
    "and recommends related items with clear reasons."
)
st.caption("Add interests, build your graph, and see exactly why each recommendation appears.")

with st.sidebar:
    st.header("TasteGraph Controls")
    user_id = st.text_input("User id", value="demo-user")
    recommendation_limit = st.slider("Recommendation count", min_value=3, max_value=10, value=5)
    seed_demo = st.button("Load demo graph", use_container_width=True)
    refresh_recommendations = st.button("Refresh recommendations", use_container_width=True)
    reset_demo = st.button("Reset demo user")
    st.caption("Tip: Load demo graph first if this user is empty.")

connection_ok = test_connection()
graph_summary = get_graph_summary(user_id)
active_database = get_database_name()
recommendation_error = None

if connection_ok:
    database_label = f" ({active_database})" if active_database else ""
    st.success(f"Connected to Neo4j{database_label}")
else:
    st.warning("Neo4j is not connected. You can still explore fallback recommendations.")

if graph_summary["source"] == "neo4j":
    st.caption(
        f"Data source: Neo4j{f' ({active_database})' if active_database else ''} | Total nodes: {graph_summary['total_nodes']} | "
        f"Current user likes: {graph_summary['liked_items']} | "
        f"Recommendation candidates: {graph_summary['recommendation_candidates']}"
    )
elif graph_summary["source"] == "error":
    st.error(f"Neo4j query failed: {graph_summary.get('error', 'Unknown error')}")
    st.caption("Data source: query error")
else:
    st.caption("Data source: fallback recommendations")

if connection_ok and not graph_summary["user_exists"]:
    st.info(
        "Neo4j is connected, but this user does not have a graph yet. Click `Load demo graph` "
        "or add an interest to create visible `User` and `LIKES` data in Neo4j."
    )

if seed_demo:
    try:
        seed_demo_graph(user_id=user_id)
        st.session_state["last_title"] = "Demo graph"
        st.session_state["last_tags"] = None
        st.success("Loaded the demo graph into Neo4j.")
        st.rerun()
    except Exception as error:
        st.error(f"Could not load demo graph: {error}")

if reset_demo:
    try:
        clear_user_graph(user_id=user_id)
        st.session_state["last_title"] = ""
        st.session_state["last_tags"] = None
        st.success("Removed the demo user's graph from Neo4j.")
        st.rerun()
    except Exception as error:
        st.error(f"Could not reset demo user: {error}")

if refresh_recommendations:
    st.rerun()

st.subheader("Add an interest")
with st.form("add_interest_form", clear_on_submit=False):
    form_left, form_right = st.columns([1.1, 1])
    with form_left:
        title = st.text_input("Title", placeholder="Reply 1988")
        media_type = st.selectbox("Media type", MEDIA_TYPES, format_func=format_media_type)
        notes = st.text_area(
            "Notes",
            placeholder="emotionally grounded, coming-of-age, soft romance",
            height=120,
        )
    with form_right:
        st.caption("Optional hints (improves tag extraction)")
        genre_hint = st.text_input("Genre", placeholder="drama")
        mood_hint = st.text_input("Mood", placeholder="nostalgic")
        theme_hint = st.text_input("Theme", placeholder="friendship")
    submit = st.form_submit_button("Add to TasteGraph", type="primary", use_container_width=True)

if submit:
    if not title.strip():
        st.error("Enter a title before adding it to the graph.")
    else:
        combined_notes = join_optional_notes(notes, genre_hint, mood_hint, theme_hint)
        tags = extract_tags(title=title, media_type=media_type, notes=combined_notes)
        try:
            add_interest(user_id=user_id, title=title, media_type=media_type, tags=tags)
            st.success(f"Saved {title} to TasteGraph.")
            st.session_state["last_tags"] = tags
            st.session_state["last_title"] = title
            st.rerun()
        except Exception as error:
            st.error(f"Could not save interest: {error}")
            st.session_state["last_tags"] = tags
            st.session_state["last_title"] = title

try:
    recommendations = get_recommendations(user_id=user_id, limit=recommendation_limit)
except Exception as error:
    recommendation_error = str(error)
    recommendations = []

if recommendation_error:
    st.error(recommendation_error)

top_reasons, recommendation_summary = build_recommendation_summary(recommendations)
best_score = max((item["score"] for item in recommendations), default=0)

status_col, count_col, score_col, likes_col = st.columns(4)
with status_col:
    st.metric("Source", graph_summary["source"].upper())
with count_col:
    st.metric("Recommendations", len(recommendations))
with score_col:
    st.metric("Top score", best_score)
with likes_col:
    st.metric("Liked items", graph_summary.get("liked_items", 0))

profile_col, explanation_col = st.columns([1.1, 1])

with profile_col:
    st.subheader("Taste profile")
    with st.container(border=True):
        if st.session_state.get("last_title"):
            st.markdown(f"### Last added: {st.session_state['last_title']}")
        profile = st.session_state.get("last_tags")
        if profile:
            st.markdown("**Genres**")
            render_tag_chips(profile.get("genres", []))
            st.markdown("**Moods**")
            render_tag_chips(profile.get("moods", []))
            st.markdown("**Themes**")
            render_tag_chips(profile.get("themes", []))
            st.markdown("**Countries**")
            render_tag_chips(profile.get("countries", []))
        else:
            st.info("Add an interest or load the demo graph to build the profile.")

with explanation_col:
    st.subheader("Why these recommendations")
    with st.container(border=True):
        st.write(recommendation_summary)
        if top_reasons:
            st.markdown(
                "Top shared signals: "
                + " | ".join(f"`{reason}` ({count})" for reason, count in top_reasons)
            )
        else:
            st.info("Recommendation explanations will appear here once the graph has enough overlap.")

st.subheader("Recommendations")
if recommendations:
    progress_base = best_score if best_score > 0 else 1
    for index, recommendation in enumerate(recommendations, start=1):
        with st.container(border=True):
            st.markdown(f"### {index}. {recommendation['title']}")
            meta_left, meta_middle, meta_right = st.columns(3)
            with meta_left:
                st.write(f"**Type:** {format_media_type(recommendation['type'])}")
            with meta_middle:
                st.write(f"**Score:** {recommendation['score']}")
            with meta_right:
                st.write(f"**Shared signals:** {len(recommendation.get('reasons', []))}")
            reasons = recommendation.get("reasons", [])
            if reasons:
                st.markdown("**Because:** " + " ".join(f"`{reason}`" for reason in reasons))
            else:
                st.write("**Because:** Shared taste signals")
            st.progress(min(recommendation["score"] / progress_base, 1.0))
else:
    st.info("No recommendations yet. Add an interest, load the demo graph, or broaden the user's taste profile.")
