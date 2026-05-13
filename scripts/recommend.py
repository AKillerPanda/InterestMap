from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.recommender import get_recommendations


if __name__ == "__main__":
    for recommendation in get_recommendations(user_id="demo-user", limit=5):
        print(
            f"{recommendation['title']} ({recommendation['type']}) "
            f"score={recommendation['score']} reasons={', '.join(recommendation['reasons'])}"
        )
