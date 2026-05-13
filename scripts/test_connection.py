from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.neo4j_client import test_connection


if __name__ == "__main__":
    print("connected" if test_connection() else "not connected")
