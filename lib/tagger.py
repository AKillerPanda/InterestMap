def extract_tags(title: str, media_type: str, notes: str = "") -> dict:
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
