import os

from dotenv import load_dotenv
from neo4j import GraphDatabase


load_dotenv()


def get_driver():
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri or not username or not password:
        return None
    return GraphDatabase.driver(uri, auth=(username, password))


def get_database_name():
    database = os.getenv("NEO4J_DATABASE", "").strip()
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
