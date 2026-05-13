from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.recommender import DEMO_ITEMS, seed_demo_graph


if __name__ == "__main__":
    seed_demo_graph()
    print(f"Seeded {len(DEMO_ITEMS)} demo items into Neo4j.")
