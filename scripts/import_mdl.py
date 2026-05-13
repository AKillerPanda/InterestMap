"""
Import a MyDramaList user's completed watch history into TasteGraph.

Usage:
    python scripts/import_mdl.py <mdl_username> [--user-id <tastegraph_user_id>]

Example:
    python scripts/import_mdl.py AkillerPanda
    python scripts/import_mdl.py AkillerPanda --user-id demo-user
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.mdl_importer import fetch_completed_dramas
from lib.recommender import add_interest
from lib.tagger import extract_tags


def main():
    args = sys.argv[1:]

    if not args or args[0].startswith("--"):
        print("Usage: python scripts/import_mdl.py <mdl_username> [--user-id <id>]")
        sys.exit(1)

    mdl_username = args[0]
    user_id = "demo-user"

    if "--user-id" in args:
        idx = args.index("--user-id")
        if idx + 1 < len(args):
            user_id = args[idx + 1]

    print(f"Fetching completed list for MDL user: {mdl_username}")
    print(f"Importing into TasteGraph user: {user_id}")
    print()

    try:
        dramas = fetch_completed_dramas(mdl_username)
    except Exception as error:
        print(f"Error: {error}")
        sys.exit(1)

    print(f"Found {len(dramas)} completed dramas. Importing...")

    imported = 0
    failed = 0

    for drama in dramas:
        title = drama["title"]
        media_type = drama["type"]
        country = drama["country"]

        notes = f"country:{country}"
        tags = extract_tags(title=title, media_type=media_type, notes=notes)

        # Preserve the actual country from MDL rather than the inferred default
        if country and country not in tags.get("countries", []):
            tags["countries"] = sorted({country.lower(), *tags.get("countries", [])})

        try:
            add_interest(user_id=user_id, title=title, media_type=media_type, tags=tags)
            print(f"  ✓ {title} ({media_type})")
            imported += 1
        except Exception as error:
            print(f"  ✗ {title} — {error}")
            failed += 1

    print()
    print(f"Done. Imported: {imported}  Failed: {failed}")


if __name__ == "__main__":
    main()
