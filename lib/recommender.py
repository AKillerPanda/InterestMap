from lib.neo4j_client import get_driver, get_session_kwargs


DEMO_USER_ID = "demo-user"


DEMO_RECOMMENDATIONS = [
    {
        "title": "Reply 1988",
        "type": "kdrama",
        "score": 5,
        "reasons": ["nostalgia", "friendship", "coming-of-age"],
    },
    {
        "title": "Heartstopper",
        "type": "graphic_novel",
        "score": 4,
        "reasons": ["friendship", "coming-of-age", "emotional"],
    },
    {
        "title": "Laufey",
        "type": "music",
        "score": 3,
        "reasons": ["dreamy", "emotional", "shared atmosphere"],
    },
]


DEMO_ITEMS = [
    {
        "title": "Reply 1988",
        "type": "kdrama",
        "liked_by_demo_user": True,
        "genres": ["drama"],
        "moods": ["nostalgia", "emotional"],
        "themes": ["friendship", "coming-of-age"],
        "countries": ["South Korea"],
    },
    {
        "title": "Twenty-Five Twenty-One",
        "type": "kdrama",
        "liked_by_demo_user": False,
        "genres": ["drama"],
        "moods": ["nostalgia", "emotional"],
        "themes": ["coming-of-age", "romance"],
        "countries": ["South Korea"],
    },
    {
        "title": "Hospital Playlist",
        "type": "kdrama",
        "liked_by_demo_user": False,
        "genres": ["drama"],
        "moods": ["warm", "emotional"],
        "themes": ["friendship", "found family"],
        "countries": ["South Korea"],
    },
    {
        "title": "Heartstopper",
        "type": "graphic_novel",
        "liked_by_demo_user": False,
        "genres": ["romance"],
        "moods": ["hopeful", "emotional"],
        "themes": ["friendship", "coming-of-age", "identity"],
        "countries": ["Global"],
    },
    {
        "title": "Blue Period",
        "type": "manga",
        "liked_by_demo_user": True,
        "genres": ["art"],
        "moods": ["introspective", "emotional"],
        "themes": ["identity", "coming-of-age"],
        "countries": ["Japan"],
    },
    {
        "title": "Your Name",
        "type": "anime",
        "liked_by_demo_user": False,
        "genres": ["romance"],
        "moods": ["dreamy", "nostalgia"],
        "themes": ["identity", "coming-of-age"],
        "countries": ["Japan"],
    },
    {
        "title": "Laufey",
        "type": "music",
        "liked_by_demo_user": False,
        "genres": ["music"],
        "moods": ["dreamy", "emotional"],
        "themes": ["nostalgia", "romance"],
        "countries": ["Global"],
    },
    {
        "title": "Mitski",
        "type": "music",
        "liked_by_demo_user": False,
        "genres": ["music"],
        "moods": ["melancholy", "emotional"],
        "themes": ["identity"],
        "countries": ["Global"],
    },
]


CONSTRAINT_STATEMENTS = [
    "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
    "CREATE CONSTRAINT item_key_unique IF NOT EXISTS FOR (i:Item) REQUIRE (i.title_key, i.type) IS UNIQUE",
    "CREATE CONSTRAINT genre_name_unique IF NOT EXISTS FOR (g:Genre) REQUIRE g.name IS UNIQUE",
    "CREATE CONSTRAINT mood_name_unique IF NOT EXISTS FOR (m:Mood) REQUIRE m.name IS UNIQUE",
    "CREATE CONSTRAINT theme_name_unique IF NOT EXISTS FOR (t:Theme) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT creator_name_unique IF NOT EXISTS FOR (c:Creator) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT country_name_unique IF NOT EXISTS FOR (c:Country) REQUIRE c.name IS UNIQUE",
]


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _normalize_key(value: str) -> str:
    return _normalize_text(value).lower()


def _normalize_media_type(value: str) -> str:
    return _normalize_key(value).replace(" ", "_")


def _normalize_tags(tags: dict) -> dict:
    cleaned = {}
    for key in ("genres", "moods", "themes", "creators", "countries"):
        values = tags.get(key, []) if isinstance(tags, dict) else []
        normalized_values = sorted(
            {_normalize_key(value) for value in values if isinstance(value, str) and value.strip()}
        )
        cleaned[key] = normalized_values
    return cleaned


def _ensure_graph_integrity(session) -> None:
    for statement in CONSTRAINT_STATEMENTS:
        session.run(statement)

    session.run(
        """
        MATCH (i:Item)
        SET i.title_key = toLower(trim(i.title)),
            i.type = toLower(trim(i.type)),
            i.title = trim(i.title)
        """
    )

    dedupe_items_cypher = """
    MATCH (i:Item)
    WITH i.title_key AS title_key, i.type AS media_type, collect(i) AS items
    WHERE title_key IS NOT NULL AND media_type IS NOT NULL AND size(items) > 1
    CALL (items) {
      WITH head(items) AS keep, tail(items) AS duplicates
      FOREACH (dup IN duplicates |
        FOREACH (u IN [(dup)<-[:LIKES]-(user) | user] | MERGE (u)-[:LIKES]->(keep))
        FOREACH (g IN [(dup)-[:HAS_GENRE]->(genre) | genre] | MERGE (keep)-[:HAS_GENRE]->(g))
        FOREACH (m IN [(dup)-[:HAS_MOOD]->(mood) | mood] | MERGE (keep)-[:HAS_MOOD]->(m))
        FOREACH (t IN [(dup)-[:HAS_THEME]->(theme) | theme] | MERGE (keep)-[:HAS_THEME]->(t))
        FOREACH (c IN [(dup)-[:CREATED_BY]->(creator) | creator] | MERGE (keep)-[:CREATED_BY]->(c))
        FOREACH (country IN [(dup)-[:FROM_COUNTRY]->(co) | co] | MERGE (keep)-[:FROM_COUNTRY]->(country))
        DETACH DELETE dup
      )
      RETURN keep
    }
    RETURN count(*) AS merged_groups
    """
    session.run(dedupe_items_cypher).consume()

    dedupe_tag_cypher_by_label = {
        "Genre": "HAS_GENRE",
        "Mood": "HAS_MOOD",
        "Theme": "HAS_THEME",
        "Creator": "CREATED_BY",
        "Country": "FROM_COUNTRY",
    }
    for label, rel_type in dedupe_tag_cypher_by_label.items():
        session.run(
            f"""
            MATCH (t:{label})
            SET t.name = toLower(trim(t.name))
            WITH toLower(trim(t.name)) AS normalized_name, collect(t) AS tags
            WHERE normalized_name IS NOT NULL AND normalized_name <> '' AND size(tags) > 1
            CALL (tags) {{
              WITH head(tags) AS keep, tail(tags) AS duplicates
              FOREACH (dup IN duplicates |
                FOREACH (i IN [(dup)<-[:{rel_type}]-(item) | item] | MERGE (i)-[:{rel_type}]->(keep))
                DETACH DELETE dup
              )
              RETURN keep
            }}
            RETURN count(*) AS merged_groups
            """
        ).consume()


def initialize_constraints() -> None:
    """Run once at app startup to create constraints only. Safe to call multiple times."""
    driver = get_driver()
    if driver is None:
        return
    try:
        with driver.session(**get_session_kwargs()) as session:
            for statement in CONSTRAINT_STATEMENTS:
                try:
                    session.run(statement)
                except Exception:
                    pass
    except Exception:
        pass


def add_interest(user_id: str, title: str, media_type: str, tags: dict) -> None:
    driver = get_driver()
    if driver is None:
        raise RuntimeError("Neo4j connection details are missing")

    normalized_title = _normalize_text(title)
    normalized_media_type = _normalize_media_type(media_type)
    normalized_tags = _normalize_tags(tags)

    cypher = """
    MERGE (u:User {id: $user_id})
    MERGE (i:Item {title_key: $title_key, type: $media_type})
    ON CREATE SET i.title = $title
    ON MATCH SET i.title = coalesce(i.title, $title)
    MERGE (u)-[:LIKES]->(i)
    WITH i
    UNWIND $genres AS genre_name
      MERGE (g:Genre {name: genre_name})
      MERGE (i)-[:HAS_GENRE]->(g)
    WITH i
    UNWIND $moods AS mood_name
      MERGE (m:Mood {name: mood_name})
      MERGE (i)-[:HAS_MOOD]->(m)
    WITH i
    UNWIND $themes AS theme_name
      MERGE (t:Theme {name: theme_name})
      MERGE (i)-[:HAS_THEME]->(t)
    WITH i
    UNWIND $countries AS country_name
      MERGE (c:Country {name: country_name})
      MERGE (i)-[:FROM_COUNTRY]->(c)
    """

    with driver.session(**get_session_kwargs()) as session:
        session.run(
            cypher,
            user_id=user_id,
            title=normalized_title,
            title_key=_normalize_key(normalized_title),
            media_type=normalized_media_type,
            genres=normalized_tags["genres"],
            moods=normalized_tags["moods"],
            themes=normalized_tags["themes"],
            countries=normalized_tags["countries"],
        )


def batch_add_interests(user_id: str, items: list[dict]) -> tuple[int, int]:
    """Import a list of {title, media_type, tags} dicts in one Neo4j transaction. Returns (imported, failed)."""
    driver = get_driver()
    if driver is None:
        raise RuntimeError("Neo4j connection details are missing")

    cypher = """
    MERGE (u:User {id: $user_id})
    WITH u
    UNWIND $items AS item
      MERGE (i:Item {title_key: item.title_key, type: item.media_type})
      ON CREATE SET i.title = item.title
      ON MATCH SET i.title = coalesce(i.title, item.title)
      MERGE (u)-[:LIKES]->(i)
      WITH i, item
      UNWIND item.genres AS genre_name
        MERGE (g:Genre {name: genre_name})
        MERGE (i)-[:HAS_GENRE]->(g)
      WITH i, item
      UNWIND item.moods AS mood_name
        MERGE (m:Mood {name: mood_name})
        MERGE (i)-[:HAS_MOOD]->(m)
      WITH i, item
      UNWIND item.themes AS theme_name
        MERGE (t:Theme {name: theme_name})
        MERGE (i)-[:HAS_THEME]->(t)
      WITH i, item
      UNWIND item.countries AS country_name
        MERGE (c:Country {name: country_name})
        MERGE (i)-[:FROM_COUNTRY]->(c)
    """

    normalized = []
    failed = 0
    for item in items:
        try:
            title = _normalize_text(item["title"])
            media_type = _normalize_media_type(item["media_type"])
            tags = _normalize_tags(item.get("tags", {}))
            normalized.append({
                "title": title,
                "title_key": _normalize_key(title),
                "media_type": media_type,
                **tags,
            })
        except Exception:
            failed += 1

    if not normalized:
        return 0, failed

    with driver.session(**get_session_kwargs()) as session:
        session.run(cypher, user_id=user_id, items=normalized)

    return len(normalized), failed


def clear_user_graph(user_id: str) -> None:
    driver = get_driver()
    if driver is None:
        raise RuntimeError("Neo4j connection details are missing")

    with driver.session(**get_session_kwargs()) as session:
        session.run("MATCH (u:User {id: $user_id}) DETACH DELETE u", user_id=user_id)
        # Remove items no longer liked by any user
        session.run(
            "MATCH (item:Item) "
            "WHERE NOT (item)<-[:LIKES|WATCHED|READ|LISTENED_TO]-() "
            "DETACH DELETE item"
        )
        # Remove orphaned tag nodes
        for label in ("Genre", "Mood", "Theme", "Creator", "Country"):
            session.run(
                f"MATCH (t:{label}) WHERE NOT (t)<-[]-() DETACH DELETE t"
            )


def get_graph_summary(user_id: str) -> dict:
    driver = get_driver()
    if driver is None:
        return {
            "source": "fallback",
            "total_nodes": 0,
            "user_exists": False,
            "liked_items": 0,
            "recommendation_candidates": 0,
        }

    summary_cypher = """
    OPTIONAL MATCH (u:User {id: $user_id})
    WITH u, u IS NOT NULL AS user_exists
    OPTIONAL MATCH (u)-[:LIKES]->(liked:Item)
    WITH u, user_exists, count(DISTINCT liked) AS liked_items
    OPTIONAL MATCH (item:Item)
    RETURN user_exists,
           liked_items,
           count(DISTINCT item) AS total_nodes
    """

    try:
        with driver.session(**get_session_kwargs()) as session:
            record = session.run(summary_cypher, user_id=user_id).single()
            if record is None:
                return {
                    "source": "neo4j",
                    "total_nodes": 0,
                    "user_exists": False,
                    "liked_items": 0,
                    "recommendation_candidates": 0,
                }
            return {
                "source": "neo4j",
                "total_nodes": record["total_nodes"],
                "user_exists": record["user_exists"],
                "liked_items": record["liked_items"],
                "recommendation_candidates": record["total_nodes"] - record["liked_items"],
            }
    except Exception as error:
        return {
            "source": "error",
            "total_nodes": 0,
            "user_exists": False,
            "liked_items": 0,
            "recommendation_candidates": 0,
            "error": str(error),
        }


def seed_demo_graph(user_id: str = DEMO_USER_ID) -> None:
    driver = get_driver()
    if driver is None:
        raise RuntimeError("Neo4j connection details are missing")

    seed_cypher = """
    MERGE (u:User {id: $user_id})
    WITH u
    UNWIND $items AS item
      MERGE (i:Item {title_key: item.title_key, type: item.type})
      ON CREATE SET i.title = item.title
      ON MATCH SET i.title = coalesce(i.title, item.title)
      FOREACH (_ IN CASE WHEN item.liked_by_demo_user THEN [1] ELSE [] END |
        MERGE (u)-[:LIKES]->(i)
      )
      WITH i, item
      UNWIND item.genres AS genre_name
        MERGE (g:Genre {name: genre_name})
        MERGE (i)-[:HAS_GENRE]->(g)
      WITH i, item
      UNWIND item.moods AS mood_name
        MERGE (m:Mood {name: mood_name})
        MERGE (i)-[:HAS_MOOD]->(m)
      WITH i, item
      UNWIND item.themes AS theme_name
        MERGE (t:Theme {name: theme_name})
        MERGE (i)-[:HAS_THEME]->(t)
      WITH i, item
      UNWIND item.countries AS country_name
        MERGE (c:Country {name: country_name})
        MERGE (i)-[:FROM_COUNTRY]->(c)
    """

    normalized_items = []
    for item in DEMO_ITEMS:
        normalized_title = _normalize_text(item["title"])
        normalized_media_type = _normalize_media_type(item["type"])
        normalized_tags = _normalize_tags(item)
        normalized_items.append(
            {
                "title": normalized_title,
                "title_key": _normalize_key(normalized_title),
                "type": normalized_media_type,
                "liked_by_demo_user": item["liked_by_demo_user"],
                "genres": normalized_tags["genres"],
                "moods": normalized_tags["moods"],
                "themes": normalized_tags["themes"],
                "countries": normalized_tags["countries"],
            }
        )

    with driver.session(**get_session_kwargs()) as session:
        session.run("MATCH (u:User {id: $user_id}) DETACH DELETE u", user_id=user_id)
        session.run(seed_cypher, user_id=user_id, items=normalized_items)


def get_liked_titles(user_id: str, limit: int = 10) -> list[str]:
    """Return titles the user has liked, most recently first."""
    driver = get_driver()
    if driver is None:
        return []
    try:
        with driver.session(**get_session_kwargs()) as session:
            result = session.run(
                "MATCH (u:User {id: $user_id})-[:LIKES]->(i:Item) "
                "RETURN i.title AS title LIMIT $limit",
                user_id=user_id,
                limit=limit,
            )
            return [r["title"] for r in result if r["title"]]
    except Exception:
        return []


def get_recommendations(
    user_id: str,
    limit: int = 5,
    offset: int = 0,
    candidate_multiplier: int = 4,
) -> list[dict]:
    driver = get_driver()
    if driver is None:
        if not DEMO_RECOMMENDATIONS:
            return []
        bounded_limit = max(1, limit)
        start = max(0, offset) % len(DEMO_RECOMMENDATIONS)
        end = start + bounded_limit
        if end <= len(DEMO_RECOMMENDATIONS):
            return DEMO_RECOMMENDATIONS[start:end]
        return DEMO_RECOMMENDATIONS[start:] + DEMO_RECOMMENDATIONS[: end - len(DEMO_RECOMMENDATIONS)]

    cypher = """
    MATCH (u:User {id: $user_id})-[:LIKES]->(liked:Item)
    MATCH (liked)-[:HAS_GENRE|HAS_MOOD|HAS_THEME|FROM_COUNTRY]->(tag)
    MATCH (rec:Item)-[:HAS_GENRE|HAS_MOOD|HAS_THEME|FROM_COUNTRY]->(tag)
    WHERE NOT (u)-[:LIKES]->(rec)
    WITH rec, collect(DISTINCT tag.name) AS reasons, count(DISTINCT tag) AS score
    RETURN rec.title AS title, rec.type AS type, score, reasons
    ORDER BY score DESC, title ASC
    SKIP $skip
    LIMIT $limit
    """

    try:
        with driver.session(**get_session_kwargs()) as session:
            bounded_limit = max(1, limit)
            result = session.run(
                cypher,
                user_id=user_id,
                skip=max(0, offset),
                limit=bounded_limit,
            )
            recommendations = [
                {
                    "title": record["title"],
                    "type": record["type"],
                    "score": record["score"],
                    "reasons": record["reasons"],
                }
                for record in result
            ]

            # If we've gone past the end, wrap back to the first page
            if not recommendations and offset > 0:
                result2 = session.run(
                    cypher,
                    user_id=user_id,
                    skip=0,
                    limit=bounded_limit,
                )
                recommendations = [
                    {
                        "title": record["title"],
                        "type": record["type"],
                        "score": record["score"],
                        "reasons": record["reasons"],
                    }
                    for record in result2
                ]

            return recommendations
    except Exception as error:
        raise RuntimeError(f"Neo4j recommendation query failed: {error}") from error
