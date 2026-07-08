"""ss.ge-ს ბინების გაყიდვის განცხადებების სქრეპერი.

გვერდზე ჩაშენებულია Next.js-ის __NEXT_DATA__ JSON ბლოკი, რომელშიც უკვე
მზა სახით ზის განცხადებების მასივი — არ სჭირდება HTML-ის პარსინგი.
საიტს არ აქვს "უახლესით დახარისხების" საიმედო URL პარამეტრი, ამიტომ
რამდენიმე გვერდს ვასქროლავთ და თარიღით ვფილტრავთ.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from .common import TBILISI, Listing, fetch_with_retry

SEARCH_URL = "https://home.ss.ge/ka/udzravi-qoneba/l/Apartments/For-Sale"
LISTING_URL = "https://home.ss.ge/ka/real-estate/l-{id}"

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)

MAX_PAGES = 20
CITY_ID_TBILISI = 95


def _parse_item(item: dict) -> Listing | None:
    try:
        price = item.get("price") or {}
        address = item.get("address") or {}
        district = address.get("subdistrictTitle") or address.get("districtTitle") or "უცნობი რაიონი"
        posted_at = datetime.fromisoformat(item["createDate"]).astimezone(TBILISI)
        floor = None
        if item.get("floorNumber") and item.get("totalAmountOfFloor"):
            floor = f"{item['floorNumber']}/{item['totalAmountOfFloor']}"

        return Listing(
            source="ss.ge",
            url=LISTING_URL.format(id=item["applicationId"]),
            district=district,
            price_usd=price.get("priceUsd"),
            area=float(item["totalArea"]),
            rooms=item.get("numberOfBedrooms"),
            floor=floor,
            posted_at=posted_at,
        )
    except (KeyError, TypeError, ValueError):
        return None


def fetch_listings(max_pages: int = MAX_PAGES) -> list[Listing]:
    """აბრუნებს ყველა დასქროლილ განცხადებას (თარიღით არაფილტრულს) —
    გამომძახებელი თავად წყვეტს, რომელია 'ახალი' და საბაზრო ფასის
    გამოსათვლელად სრული ნიმუშიც სჭირდება."""
    results: list[Listing] = []

    for page in range(1, max_pages + 1):
        resp = fetch_with_retry(
            SEARCH_URL,
            params={"cityIdList": CITY_ID_TBILISI, "page": page},
        )
        match = NEXT_DATA_RE.search(resp.text)
        if not match:
            break

        data = json.loads(match.group(1))
        items = (
            data.get("props", {})
            .get("pageProps", {})
            .get("applicationList", {})
            .get("realStateItemModel", [])
        )
        if not items:
            break

        for raw in items:
            listing = _parse_item(raw)
            if listing:
                results.append(listing)

    return results
