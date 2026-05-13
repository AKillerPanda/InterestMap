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


def _extract_tags_llm(title: str, media_type: str, notes: str) -> dict | None:
    api_key = _first_env(
        "KIMCHI_API_KEY",
        "kimi-k2.6_api_key",
        "Kimchi_api_key",
        "OPENAI_API_KEY",
    )
    if not api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=_first_env("KIMCHI_BASE_URL", "kimi-k2.6_url") or "https://llm.kimchi.dev/openai/v1",
        )

        prompt = (
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

        response = client.chat.completions.create(
            model=_first_env("KIMCHI_MODEL") or "kimi-k2.6",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        tags = json.loads(raw)

        for key in ("genres", "moods", "themes", "creators", "countries"):
            if key not in tags or not isinstance(tags[key], list):
                tags[key] = []
        return tags

    except Exception:
        return None


def extract_tags(title: str, media_type: str, notes: str = "") -> dict:
    llm_tags = _extract_tags_llm(title, media_type, notes)
    if llm_tags:
        for key in ("genres", "moods", "themes", "creators", "countries"):
            llm_tags[key] = sorted({v.lower().strip() for v in llm_tags[key] if isinstance(v, str) and v.strip()})
        if not llm_tags["genres"]:
            llm_tags["genres"] = [media_type]
        if not llm_tags["moods"]:
            llm_tags["moods"] = ["thoughtful"]
        if not llm_tags["themes"]:
            llm_tags["themes"] = ["shared taste"]
        if not llm_tags["countries"]:
            llm_tags["countries"] = ["Global"]
        return llm_tags

    text = f"{title} {media_type} {notes}".lower()

    genres = []
    moods = []
    themes = []
    creators = []
    countries = []

    if any(word in text for word in ["nostalgia", "nostalgic", "retro", "memory"]):
        moods.append("nostalgia")
    if any(word in text for word in ["friend", "friendship", "found family"]):
        themes.append("friendship")
    if any(word in text for word in ["coming-of-age", "youth", "growing up", "teen"]):
        themes.append("coming-of-age")
    if any(word in text for word in ["emotional", "melancholy", "sad", "heart"]):
        moods.append("emotional")
    if any(word in text for word in ["dreamy", "dream", "soft"]):
        moods.append("dreamy")
    if any(word in text for word in ["romance", "love", "dating"]):
        themes.append("romance")
    if any(word in text for word in ["identity", "self", "purpose"]):
        themes.append("identity")
    if any(word in text for word in ["art", "creative", "painting"]):
        genres.append("art")

    if media_type in {"kdrama", "anime", "movie", "tv_show"}:
        countries.append("South Korea" if media_type == "kdrama" else "Japan" if media_type == "anime" else "Global")
    elif media_type in {"book", "graphic_novel", "manga"}:
        countries.append("Global")
    elif media_type == "music":
        genres.append("music")

    if not genres:
        genres.append(media_type)
    if not moods:
        moods.append("thoughtful")
    if not themes:
        themes.append("shared taste")
    if not countries:
        countries.append("Global")

    return {
        "genres": sorted(set(genres)),
        "moods": sorted(set(moods)),
        "themes": sorted(set(themes)),
        "creators": sorted(set(creators)),
        "countries": sorted(set(countries)),
    }
