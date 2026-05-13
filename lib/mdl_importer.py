"""
Fetch a user's completed drama list from their public MyDramaList profile.

Uses cloudscraper to bypass Cloudflare and BeautifulSoup to parse the page.
Returns a list of dicts with title, type, country, and year for each item.
"""

import cloudscraper
from bs4 import BeautifulSoup


MDL_BASE = "https://mydramalist.com"
_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://mydramalist.com",
}

_TYPE_MAP = {
    "drama": "kdrama",
    "movie": "movie",
    "film": "movie",
    "special": "tv_show",
    "mini series": "tv_show",
    "tv series": "tv_show",
    "anime": "anime",
}

_COUNTRY_NORMALISE = {
    "south korea": "South Korea",
    "korea": "South Korea",
    "japan": "Japan",
    "china": "China",
    "taiwan": "Taiwan",
    "thailand": "Thailand",
    "philippines": "Philippines",
    "hong kong": "Hong Kong",
    "vietnam": "Vietnam",
    "indonesia": "Indonesia",
    "united states": "Global",
    "usa": "Global",
}


def _scraper():
    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )


def _normalise_country(raw: str) -> str:
    key = raw.strip().lower()
    return _COUNTRY_NORMALISE.get(key, raw.strip() or "Global")


def _infer_type(raw_type: str, country: str) -> str:
    key = raw_type.strip().lower()
    media_type = _TYPE_MAP.get(key, "tv_show")
    if key == "drama":
        if country == "South Korea":
            return "kdrama"
        if country == "Japan":
            return "tv_show"
    return media_type


def _parse_list_table(table) -> list[dict]:
    items = []
    for row in table.find_all("tr"):
        title_td = row.find("td", class_="mdl-style-col-title")
        if not title_td:
            continue
        a = title_td.find("a")
        if not a:
            continue
        title = a.get_text(strip=True)
        if not title:
            continue

        country_td = row.find("td", class_="mdl-style-col-country")
        raw_country = country_td.get_text(strip=True) if country_td else ""
        country = _normalise_country(raw_country)

        type_td = row.find("td", class_="mdl-style-col-type")
        raw_type = type_td.get_text(strip=True) if type_td else "Drama"
        media_type = _infer_type(raw_type, country)

        year_td = row.find("td", class_="mdl-style-col-year")
        year = year_td.get_text(strip=True) if year_td else ""

        items.append({"title": title, "type": media_type, "country": country, "year": year})

    return items


def fetch_completed_dramas(username: str) -> list[dict]:
    """
    Fetch the completed drama list for a public MDL username.

    Returns a list of dicts: {title, type, country, year}
    Raises RuntimeError with a user-friendly message on failure.
    """
    if not username or not username.strip():
        raise ValueError("Username cannot be empty")

    username = username.strip()
    url = f"{MDL_BASE}/dramalist/{username}"

    try:
        response = _scraper().get(url, headers=_HEADERS, timeout=20)
    except Exception as error:
        raise RuntimeError(
            f"Could not reach MyDramaList for '{username}'. Check your internet connection. ({error})"
        ) from error

    if response.status_code == 404:
        raise RuntimeError(f"MDL user '{username}' not found. Check the spelling.")
    if response.status_code == 403:
        raise RuntimeError("MyDramaList blocked the request. Try again in a few seconds.")
    if response.status_code != 200:
        raise RuntimeError(f"MyDramaList returned HTTP {response.status_code} for user '{username}'.")

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the Completed section by walking labels
    completed_table = None
    for label in soup.select(".mdl-style-list-label"):
        if label.get_text(strip=True).lower() == "completed":
            for sibling in label.find_all_next():
                if sibling.name == "table":
                    completed_table = sibling
                    break
            break

    # Fallback: list_2 is consistently the completed table
    if completed_table is None:
        completed_table = soup.find("table", id="list_2")

    if completed_table is None:
        raise RuntimeError(
            f"No completed list found for '{username}'. The profile may be private or the completed list may be empty."
        )

    items = _parse_list_table(completed_table)

    if not items:
        raise RuntimeError(f"No completed dramas found for '{username}'. The completed list appears to be empty.")

    return items
