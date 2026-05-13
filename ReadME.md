# TasteGraph

TasteGraph maps what you love across books, manga, shows, films, and music, then recommends related media with explanations.

## What Works Now

- Streamlit UI for entering interests and viewing explainable recommendations
- Neo4j-backed graph storage for users, items, and shared taste signals
- Demo graph seeding from the UI or terminal
- Fallback scripts for connection checks, seeding, and recommendation output

## Stack

- Python
- Streamlit
- Neo4j Python Driver
- python-dotenv

## Setup

1. Ensure your existing `.env` defines `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run the app with `streamlit run app.py`.

## Demo Flow

1. Start the app.
2. Click `Load demo graph` in the sidebar.
3. Review the recommendation cards and explanation panel.
4. Add your own interest to extend the graph for the current user.

## VS Code Launching

- Use the `TasteGraph: Run Streamlit` task from the Command Palette or Terminal task picker.
- Use the `TasteGraph Streamlit` launch configuration to debug the app from VS Code.

## Fallback scripts

- `python scripts/test_connection.py`
- `python scripts/seed.py`
- `python scripts/recommend.py`

## Notes

- `scripts/seed.py` clears and recreates the demo user's likes before reseeding.
- If Neo4j is unavailable, the app falls back to static recommendations so the UI still loads.
