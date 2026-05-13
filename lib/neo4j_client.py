import os

from dotenv import load_dotenv
from neo4j import GraphDatabase


load_dotenv()


def _first_env(*keys: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value and value.strip():
            return value.strip()
    return ""


def _derive_neo4j_uri_from_query_url(query_url: str) -> str:
    # Example:
    # https://<instance>.databases.neo4j.io/db/<db>/query/v2 -> neo4j+s://<instance>.databases.neo4j.io
    if not query_url:
        return ""

    try:
        host_part = query_url.split("://", 1)[1].split("/", 1)[0].strip()
    except Exception:
        return ""

    if not host_part:
        return ""
    return f"neo4j+s://{host_part}"


def get_driver():
    uri = _first_env("NEO4J_URI")
    if not uri:
        uri = _derive_neo4j_uri_from_query_url(_first_env("NEO4J_queryAPI_URL"))

    username = _first_env("NEO4J_USERNAME") or "neo4j"
    password = _first_env("NEO4J_PASSWORD")
    if not uri or not username or not password:
        return None
    return GraphDatabase.driver(uri, auth=(username, password))


def get_database_name():
    database = _first_env("NEO4J_DATABASE", "AURA_INSTANCEID")
    return database or None


def get_session_kwargs():
    database = get_database_name()
    return {"database": database} if database else {}


def test_connection() -> bool:
    driver = get_driver()
    if driver is None:
        return False

    try:
        with driver.session(**get_session_kwargs()) as session:
            session.run("RETURN 1 AS ok").single()
        return True
    except Exception:
        return False
    finally:
        driver.close()
