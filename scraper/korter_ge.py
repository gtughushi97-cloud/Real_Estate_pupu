"""korter.ge-ს ბინების გაყიდვის განცხადებების სქრეპერი.

გვერდზე ჩაშენებულია `window.INITIAL_STATE = {...}` ბლოკი დიდი raw JS
ობიექტით (არა სუფთა <script type="application/json">), ამიტომ მისი
ამოღება ხდება ფრჩხილების დაბალანსებული სკანირებით (მარტივი regex ვერ
გაუმკლავდება ჩადგმულ სტრიქონებს/ფრჩხილებს).
"""

from __future__ import annotations

import json
from datetime import datetime

from .common import TBILISI, Listing, fetch_with_retry

SEARCH_URL = "https://korter.ge/binebis-yidva-gayidva-tbilisi"
LISTING_URL = "https://korter.ge{link}"

STATE_MARKER = "window.INITIAL_STATE = "

MAX_PAGES = 8

# GEL-დან USD-ში მიახლოებითი კურსი (Korter ზოგ განცხადებას ლარში აჩვენებს).
GEL_TO_USD_RATE = 2.65


def _extract_initial_state(html: str) -> dict | None:
    start_idx = html.find(STATE_MARKER)
    if start_idx == -1:
        return None
    start = start_idx + len(STATE_MARKER)

    depth = 0
    in_string = False
    escape = False
    quote_char = ""
    end = -1

    for i in range(start, len(html)):
        ch = html[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote_char:
                in_string = False
        else:
            if ch in ('"', "'"):
                in_string = True
                quote_char = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

    if end == -1:
        return None

    try:
        return json.loads(html[start:end])
    except json.JSONDecodeError:
        return None


def _parse_item(item: dict) -> Listing | None:
    try:
        price = item.get("price")
        currency = item.get("currency")
        price_usd = None
        if price is not None:
            if currency == "USD":
                price_usd = float(price)
            elif currency == "GEL":
                price_usd = round(float(price) / GEL_TO_USD_RATE)

        posted_at = datetime.fromisoformat(item["actualizeTime"]).astimezone(TBILISI)

        floor = None
        floor_numbers = item.get("floorNumbers") or []
        total_floors = (item.get("house") or {}).get("floorCount")
        if floor_numbers and total_floors:
            floor = f"{floor_numbers[0]}/{total_floors}"

        district = item.get("subLocalityNominative") or "უცნობი რაიონი"

        return Listing(
            source="korter.ge",
            url=LISTING_URL.format(link=item["link"]),
            district=district,
            price_usd=price_usd,
            area=float(item["area"]),
            rooms=item.get("roomCount"),
            floor=floor,
            posted_at=posted_at,
        )
    except (KeyError, TypeError, ValueError):
        return None


def fetch_listings(max_pages: int = MAX_PAGES) -> list[Listing]:
    results: list[Listing] = []

    for page in range(1, max_pages + 1):
        params = {"page": page} if page > 1 else None
        resp = fetch_with_retry(SEARCH_URL, params=params)

        state = _extract_initial_state(resp.text)
        if not state:
            break

        items = (state.get("apartmentListingStore") or {}).get("apartments") or []
        if not items:
            break

        for raw in items:
            listing = _parse_item(raw)
            if listing:
                results.append(listing)

    return results
