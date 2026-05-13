from collections import Counter

import streamlit as st

from lib.mdl_importer import fetch_completed_dramas
from lib.neo4j_client import get_database_name, test_connection
from lib.recommender import (
    add_interest,
    batch_add_interests,
    clear_user_graph,
    get_graph_summary,
    get_liked_titles,
    get_recommendations,
    initialize_constraints,
    seed_demo_graph,
)
from lib.tagger import extract_tags, generate_explanation, get_active_provider


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


def render_tag_chips(values: list[str]) -> None:
    if not values:
        st.write("None yet")
        return
    st.markdown(" ".join(f"`{v}`" for v in values))


def build_signal_summary(recommendations: list[dict]) -> tuple[list[tuple[str, int]], str]:
    reason_counts = Counter(
        reason
        for rec in recommendations
        for reason in rec.get("reasons", [])
    )
    top = reason_counts.most_common(3)
    if not top:
        return top, "Add more interests to generate explanation signals."
    summary = ", ".join(r for r, _ in top)
    return top, f"Your strongest cross-media signals are **{summary}**."


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(page_title="TasteGraph", page_icon="🎯", layout="wide")

if "constraints_initialized" not in st.session_state:
    initialize_constraints()
    st.session_state["constraints_initialized"] = True

st.session_state.setdefault("last_tags", None)
st.session_state.setdefault("last_title", "")
st.session_state.setdefault("recommendation_offset", 0)
st.session_state.setdefault("recommendation_user", "")
st.session_state.setdefault("llm_explanation", None)


@st.cache_data(ttl=60)
def cached_test_connection() -> bool:
    return test_connection()


@st.cache_data(ttl=30)
def cached_graph_summary(uid: str) -> dict:
    return get_graph_summary(uid)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🎯 TasteGraph")
st.write(
    "TasteGraph maps what you love across books, shows, manga, films, and music "
    "— then recommends new things with clear, graph-powered explanations."
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Controls")
    user_id = st.text_input("User ID", value="demo-user")
    recommendation_limit = st.slider("Recommendations to show", min_value=3, max_value=15, value=5)

    st.divider()
    seed_demo = st.button("🌱 Load demo graph", use_container_width=True)
    refresh_recommendations = st.button("🔀 Refresh recommendations", use_container_width=True)
    reset_demo = st.button("🗑️ Reset this user", use_container_width=True)

    st.divider()
    active_provider = get_active_provider()
    st.caption(f"🤖 LLM: **{active_provider}**")
    st.caption("Kimi-K2.6 → OpenAI → rule-based fallback")

# Reset offset when user switches
if st.session_state["recommendation_user"] != user_id:
    st.session_state["recommendation_user"] = user_id
    st.session_state["recommendation_offset"] = 0
    st.session_state["llm_explanation"] = None

connection_ok = cached_test_connection()
graph_summary = cached_graph_summary(user_id)
active_database = get_database_name()
recommendation_error = None

# Connection status banner
if connection_ok:
    db_label = f" · `{active_database}`" if active_database else ""
    st.success(f"✅ Connected to Neo4j{db_label} · {graph_summary.get('total_nodes', 0)} nodes · {graph_summary.get('liked_items', 0)} liked items for `{user_id}`")
else:
    st.warning("⚠️ Neo4j not connected — showing fallback recommendations.")

if connection_ok and not graph_summary["user_exists"]:
    st.info("This user has no graph yet. Click **Load demo graph** or add an interest below.")

# ---------------------------------------------------------------------------
# Button actions
# ---------------------------------------------------------------------------
if seed_demo:
    try:
        seed_demo_graph(user_id=user_id)
        st.session_state.update(last_title="Demo graph", last_tags=None, recommendation_offset=0, llm_explanation=None)
        cached_graph_summary.clear()
        st.success("Demo graph loaded.")
        st.rerun()
    except Exception as e:
        st.error(f"Could not load demo graph: {e}")

if reset_demo:
    try:
        clear_user_graph(user_id=user_id)
        st.session_state.update(last_title="", last_tags=None, recommendation_offset=0, llm_explanation=None)
        cached_graph_summary.clear()
        st.success("User graph cleared.")
        st.rerun()
    except Exception as e:
        st.error(f"Could not reset: {e}")

if refresh_recommendations:
    st.session_state["recommendation_offset"] += recommendation_limit
    st.session_state["llm_explanation"] = None
    st.rerun()

# ---------------------------------------------------------------------------
# MDL import
# ---------------------------------------------------------------------------
st.subheader("📺 Import from MyDramaList")
with st.form("mdl_import_form", clear_on_submit=False):
    mdl_col1, mdl_col2 = st.columns([2, 1])
    with mdl_col1:
        mdl_username = st.text_input("MDL username", placeholder="YourMDLUsername")
    with mdl_col2:
        st.write("")
        st.write("")
        mdl_submit = st.form_submit_button("Import completed list", use_container_width=True)

if mdl_submit:
    if not mdl_username.strip():
        st.error("Enter your MyDramaList username.")
    else:
        with st.spinner(f"Fetching completed list for **{mdl_username}**..."):
            try:
                dramas = fetch_completed_dramas(mdl_username.strip())
            except Exception as e:
                dramas = []
                st.error(str(e))

        if dramas:
            provider = get_active_provider()
            with st.spinner(f"Tagging {len(dramas)} titles via {provider}..."):
                items_to_import = []
                for drama in dramas:
                    tags = extract_tags(drama["title"], drama["type"], f"country:{drama['country']}")
                    if drama["country"] and drama["country"].lower() not in tags.get("countries", []):
                        tags["countries"] = sorted({drama["country"].lower(), *tags.get("countries", [])})
                    items_to_import.append({"title": drama["title"], "media_type": drama["type"], "tags": tags})

            with st.spinner("Saving to Neo4j..."):
                try:
                    imported, failed = batch_add_interests(user_id=user_id, items=items_to_import)
                    cached_graph_summary.clear()
                    st.success(f"✅ Imported **{imported}** titles from `{mdl_username}` — {failed} failed.")
                    st.session_state.update(
                        last_title=f"MDL: {mdl_username}",
                        last_tags=None,
                        recommendation_offset=0,
                        llm_explanation=None,
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Import failed: {e}")

# ---------------------------------------------------------------------------
# Add interest form
# ---------------------------------------------------------------------------
st.divider()
st.subheader("➕ Add an interest")
with st.form("add_interest_form", clear_on_submit=False):
    form_left, form_right = st.columns([1.2, 1])
    with form_left:
        title = st.text_input("Title", placeholder="Reply 1988")
        media_type = st.selectbox("Media type", MEDIA_TYPES, format_func=format_media_type)
        notes = st.text_area("Notes / hints", placeholder="emotionally grounded, coming-of-age, soft romance", height=100)
    with form_right:
        st.caption("Optional — improves LLM tag extraction")
        genre_hint = st.text_input("Genre hint", placeholder="drama")
        mood_hint = st.text_input("Mood hint", placeholder="nostalgic")
        theme_hint = st.text_input("Theme hint", placeholder="friendship")
    submit = st.form_submit_button("Add to TasteGraph", type="primary", use_container_width=True)

if submit:
    if not title.strip():
        st.error("Enter a title.")
    else:
        combined_notes = join_optional_notes(notes, genre_hint, mood_hint, theme_hint)
        with st.spinner(f"Tagging **{title}** via {get_active_provider()}..."):
            tags = extract_tags(title=title, media_type=media_type, notes=combined_notes)
        try:
            add_interest(user_id=user_id, title=title, media_type=media_type, tags=tags)
            st.success(f"Saved **{title}** to TasteGraph.")
            st.session_state.update(last_tags=tags, last_title=title, recommendation_offset=0, llm_explanation=None)
            cached_graph_summary.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Could not save: {e}")
            st.session_state.update(last_tags=tags, last_title=title)

# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------
try:
    recommendations = get_recommendations(
        user_id=user_id,
        limit=recommendation_limit,
        offset=st.session_state["recommendation_offset"],
    )
except Exception as e:
    recommendation_error = str(e)
    recommendations = []

if recommendation_error:
    st.error(recommendation_error)

top_signals, signal_summary = build_signal_summary(recommendations)
best_score = max((r["score"] for r in recommendations), default=0)

# Status bar
m1, m2, m3, m4 = st.columns(4)
m1.metric("Data source", graph_summary["source"].upper())
m2.metric("Recommendations", len(recommendations))
m3.metric("Top score", best_score)
m4.metric("Liked items", graph_summary.get("liked_items", 0))

st.divider()

# Taste profile + explanation side by side
profile_col, explanation_col = st.columns([1.1, 1])

with profile_col:
    st.subheader("🗂️ Taste profile")
    with st.container(border=True):
        last_title = st.session_state.get("last_title")
        if last_title:
            st.markdown(f"**Last added:** {last_title}")
        profile = st.session_state.get("last_tags")
        if profile:
            for label, key in [("Genres", "genres"), ("Moods", "moods"), ("Themes", "themes"), ("Countries", "countries")]:
                st.markdown(f"**{label}**")
                render_tag_chips(profile.get(key, []))
        else:
            st.info("Add an interest or load the demo graph.")

with explanation_col:
    st.subheader("💡 Why these recommendations")
    with st.container(border=True):
        if top_signals:
            st.markdown(signal_summary)
            st.markdown(
                "Top signals: " + " · ".join(f"`{r}` ×{c}" for r, c in top_signals)
            )
            st.divider()

        # LLM-generated explanation (cached in session state)
        if recommendations and graph_summary.get("liked_items", 0) > 0:
            if st.session_state["llm_explanation"] is None:
                user_liked = get_liked_titles(user_id, limit=10)
                with st.spinner("Generating explanation..."):
                    explanation = generate_explanation(recommendations, user_liked)
                st.session_state["llm_explanation"] = explanation or ""
            if st.session_state["llm_explanation"]:
                st.markdown(st.session_state["llm_explanation"])
            else:
                st.caption("LLM explanation unavailable — showing graph signals above.")
        else:
            st.info("Explanations appear once the graph has liked items and recommendations.")

# Recommendation cards
st.subheader("🎬 Recommendations")
if recommendations:
    progress_base = best_score if best_score > 0 else 1
    for i, rec in enumerate(recommendations, start=1):
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            with c1:
                st.markdown(f"### {i}. {rec['title']}")
            with c2:
                st.metric("Type", format_media_type(rec["type"]))
            with c3:
                st.metric("Score", rec["score"])
            with c4:
                st.metric("Signals", len(rec.get("reasons", [])))
            reasons = rec.get("reasons", [])
            if reasons:
                st.markdown("**Because:** " + " ".join(f"`{r}`" for r in reasons))
            st.progress(min(rec["score"] / progress_base, 1.0))
else:
    st.info("No recommendations yet — add interests, load the demo graph, or refresh.")

