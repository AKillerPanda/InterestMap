import json
import os

from dotenv import load_dotenv

load_dotenv()


def _first_env(*keys: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value and value.strip():
            return value.strip()
    return ""


# ---------------------------------------------------------------------------
# Provider detection — called once, results exposed for UI display
# ---------------------------------------------------------------------------

def get_kimchi_credentials() -> tuple[str, str]:
    """Return (api_key, base_url) for Kimchi/Kimi-K2.6, or ('', '') if unavailable."""
    key = _first_env("kimi-k2.6_api_key", "Kimchi_api_key", "KIMCHI_API_KEY")
    url = _first_env("kimi-k2.6_url", "KIMCHI_BASE_URL") or "https://llm.kimchi.dev/openai/v1"
    return key, url


def get_openai_credentials() -> tuple[str, str]:
    """Return (api_key, base_url) for OpenAI, or ('', '') if unavailable."""
    key = _first_env("openai_api_key", "OPENAI_API_KEY")
    return key, "https://api.openai.com/v1"


def get_active_provider() -> str:
    """Return a display label for the active LLM provider."""
    if get_kimchi_credentials()[0]:
        return "Kimi-K2.6 (Kimchi)"
    if get_openai_credentials()[0]:
        return "OpenAI GPT-4o-mini"
    return "Rule-based fallback"


# ---------------------------------------------------------------------------
# Internal LLM helpers
# ---------------------------------------------------------------------------

def _call_llm(prompt: str, api_key: str, base_url: str, model: str) -> str | None:
    """Make a single chat completion call. Returns raw text or None on failure."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return None


def _parse_json_tags(raw: str) -> dict | None:
    """Parse LLM output as a JSON tag dict. Returns None if unparseable."""
    if not raw:
        return None
    # Strip markdown fences
    text = raw
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    try:
        tags = json.loads(text.strip())
        for key in ("genres", "moods", "themes", "creators", "countries"):
            if key not in tags or not isinstance(tags[key], list):
                tags[key] = []
        return tags
    except Exception:
        return None


def _tag_prompt(title: str, media_type: str, notes: str) -> str:
    return (
        f"You are a media tagging assistant. Given a title, media type, and optional notes, "
        f"extract relevant tags and return them as JSON.\n\n"
        f"Title: {title}\n"
        f"Media type: {media_type}\n"
        f"Notes: {notes or 'none'}\n\n"
        f"Return ONLY a JSON object with these exact keys:\n"
        f"  genres: list of genre strings\n"
        f"  moods: list of mood strings (e.g. nostalgic, dreamy, melancholy)\n"
        f"  themes: list of theme strings (e.g. coming-of-age, friendship, identity)\n"
        f"  creators: list of creator/director/author names if known\n"
        f"  countries: list of country names\n\n"
        f"Keep each list to 1-4 items. Use lowercase. Return valid JSON only."
    )


# ---------------------------------------------------------------------------
# Tag extraction — Kimi-K2.6 → OpenAI → rule-based
# ---------------------------------------------------------------------------

def _extract_tags_kimchi(title: str, media_type: str, notes: str) -> dict | None:
    key, url = get_kimchi_credentials()
    if not key:
        return None
    raw = _call_llm(_tag_prompt(title, media_type, notes), key, url, "kimi-k2.6")
    return _parse_json_tags(raw)


def _extract_tags_openai(title: str, media_type: str, notes: str) -> dict | None:
    key, url = get_openai_credentials()
    if not key:
        return None
    raw = _call_llm(_tag_prompt(title, media_type, notes), key, url, "gpt-4o-mini")
    return _parse_json_tags(raw)


def _extract_tags_rules(title: str, media_type: str, notes: str) -> dict:
    text = f"{title} {media_type} {notes}".lower()

    genres, moods, themes, creators, countries = [], [], [], [], []

    if any(w in text for w in ["nostalgia", "nostalgic", "retro", "memory"]):
        moods.append("nostalgia")
    if any(w in text for w in ["friend", "friendship", "found family"]):
        themes.append("friendship")
    if any(w in text for w in ["coming-of-age", "youth", "growing up", "teen"]):
        themes.append("coming-of-age")
    if any(w in text for w in ["emotional", "melancholy", "sad", "heart"]):
        moods.append("emotional")
    if any(w in text for w in ["dreamy", "dream", "soft"]):
        moods.append("dreamy")
    if any(w in text for w in ["romance", "love", "dating"]):
        themes.append("romance")
    if any(w in text for w in ["identity", "self", "purpose"]):
        themes.append("identity")
    if any(w in text for w in ["art", "creative", "painting"]):
        genres.append("art")

    if media_type == "kdrama":
        countries.append("south korea")
    elif media_type == "anime":
        countries.append("japan")
    elif media_type == "music":
        genres.append("music")

    if not genres:
        genres.append(media_type)
    if not moods:
        moods.append("thoughtful")
    if not themes:
        themes.append("shared taste")
    if not countries:
        countries.append("global")

    return {
        "genres": sorted(set(genres)),
        "moods": sorted(set(moods)),
        "themes": sorted(set(themes)),
        "creators": sorted(set(creators)),
        "countries": sorted(set(countries)),
    }


def _normalise_tags(tags: dict) -> dict:
    result = {}
    for key in ("genres", "moods", "themes", "creators", "countries"):
        result[key] = sorted({v.lower().strip() for v in tags.get(key, []) if isinstance(v, str) and v.strip()})
    if not result["genres"]:
        result["genres"] = ["general"]
    if not result["moods"]:
        result["moods"] = ["thoughtful"]
    if not result["themes"]:
        result["themes"] = ["shared taste"]
    if not result["countries"]:
        result["countries"] = ["global"]
    return result


def extract_tags(title: str, media_type: str, notes: str = "") -> dict:
    """Extract tags using best available provider: Kimi-K2.6 → OpenAI → rules."""
    tags = _extract_tags_kimchi(title, media_type, notes)
    if tags is None:
        tags = _extract_tags_openai(title, media_type, notes)
    if tags is None:
        tags = _extract_tags_rules(title, media_type, notes)
    return _normalise_tags(tags)


# ---------------------------------------------------------------------------
# LLM-enhanced recommendation explanation
# ---------------------------------------------------------------------------

def generate_explanation(recommendations: list[dict], user_interests: list[str]) -> str | None:
    """
    Use the best available LLM to produce a one-paragraph natural-language
    explanation of why these recommendations fit this user's taste graph.
    Returns None if no LLM is available or the call fails.
    """
    if not recommendations:
        return None

    rec_lines = "\n".join(
        f"- {r['title']} ({r['type']}): shared signals = {', '.join(r.get('reasons', []))}"
        for r in recommendations[:5]
    )
    interest_text = ", ".join(user_interests[:10]) if user_interests else "various titles"

    prompt = (
        f"You are TasteGraph, an explainable cross-media recommendation system.\n\n"
        f"The user likes: {interest_text}\n\n"
        f"Top recommendations:\n{rec_lines}\n\n"
        f"Write 2-3 sentences explaining WHY these recommendations fit this user's taste. "
        f"Be specific about shared moods, themes, and genres. "
        f"Be concise and enthusiastic. Do not use bullet points."
    )

    kimchi_key, kimchi_url = get_kimchi_credentials()
    if kimchi_key:
        result = _call_llm(prompt, kimchi_key, kimchi_url, "kimi-k2.6")
        if result:
            return result

    openai_key, openai_url = get_openai_credentials()
    if openai_key:
        result = _call_llm(prompt, openai_key, openai_url, "gpt-4o-mini")
        if result:
            return result

    return None

