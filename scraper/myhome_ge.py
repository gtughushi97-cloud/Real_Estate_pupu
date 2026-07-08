"""myhome.ge-ს ბინების გაყიდვის განცხადებების სქრეპერი.

გვერდი აშენებულია Next.js-ზე და შეიცავს __NEXT_DATA__ JSON ბლოკს, სადაც
react-query-ის dehydrated state-ში უკვე ჩამოტვირთულია განცხადებების
სია — ვპარსავთ პირდაპირ, HTML-ის გარეშე.

საიტს აქვს Cloudflare-ის ბოტ-დაცვა, რომელიც ზოგჯერ (განსაკუთრებით
გაზიარებული/დატაცენტრის IP-ებიდან, როგორიცაა GitHub Actions) შეიძლება
დაბლოკოს მოთხოვნა. ასეთ შემთხვევაში ეს მოდული უბრალოდ ცარიელ სიას
აბრუნებს და ცდომილებას აღნიშნავს — დანარჩენი წყაროები მაინც გაგრძელდება.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from .common import TBILISI, Listing, fetch_with_retry

SEARCH_URL = "https://www.myhome.ge/en/s/Apartments-For-Sale-Tbilisi/"
LISTING_URL = "https://www.myhome.ge/en/real-estate/{id}/"

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)

DEAL_TYPE_FOR_SALE = 1

DISTRICT_TRANSLATIONS = {
    "vake": "ვაკე",
    "saburtalo": "საბურთალო",
    "vera": "ვერა",
    "mtatsminda": "მთაწმინდა",
    "sololaki": "სოლოლაკი",
    "old tbilisi": "ძველი თბილისი",
    "chugureti": "ჩუღურეთი",
    "didube": "დიდუბე",
    "nadzaladevi": "ნაძალადევი",
    "gldani": "გლდანი",
    "isani": "ისანი",
    "samgori": "სამგორი",
    "ortachala": "ორთაჭალა",
    "avlabari": "ავლაბარი",
    "varketili": "ვარკეთილი",
    "didi digomi": "დიდი დიღომი",
    "digomi": "დიღომი",
    "nutsubidze plateau": "ნუცუბიძის ფერდობი",
    "vazisubani": "ვაზისუბანი",
    "temka": "თემქა",
    "lisi": "ლისი",
    "krtsanisi": "კრწანისი",
    "didgori": "დიდგორი",
    "kukia": "კუკია",
    "navtlughi": "ნავთლუღი",
    "dighomi": "დიღომი",
}


class MyHomeBlockedError(Exception):
    pass


def _translate_district(name: str) -> str:
    if not name:
        return "უცნობი რაიონი"
    return DISTRICT_TRANSLATIONS.get(name.strip().lower(), name)


def _parse_item(item: dict) -> Listing | None:
    try:
        if item.get("deal_type_id") != DEAL_TYPE_FOR_SALE:
            return None

        price_block = (item.get("price") or {}).get("2") or {}
        price_usd = price_block.get("price_total")

        posted_at = datetime.strptime(item["last_updated"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TBILISI)

        floor = None
        if item.get("floor") and item.get("total_floors"):
            floor = f"{item['floor']}/{item['total_floors']}"

        return Listing(
            source="myhome.ge",
            url=LISTING_URL.format(id=item["id"]),
            district=_translate_district(item.get("urban_name") or item.get("district_name") or ""),
            price_usd=price_usd,
            area=float(item["area"]),
            rooms=None,
            floor=floor,
            posted_at=posted_at,
        )
    except (KeyError, TypeError, ValueError):
        return None


def fetch_listings() -> list[Listing]:
    resp = fetch_with_retry(SEARCH_URL)

    if "cf_chl_opt" in resp.text or "Just a moment" in resp.text:
        raise MyHomeBlockedError("Cloudflare-მ დაბლოკა მოთხოვნა")

    match = NEXT_DATA_RE.search(resp.text)
    if not match:
        raise MyHomeBlockedError("__NEXT_DATA__ ბლოკი ვერ მოიძებნა")

    data = json.loads(match.group(1))
    queries = (
        data.get("props", {})
        .get("pageProps", {})
        .get("dehydratedState", {})
        .get("queries", [])
    )

    items: list[dict] = []
    for query in queries:
        key = query.get("queryKey", [])
        if len(key) >= 2 and key[0] == "statements" and key[1] == "list":
            items = query.get("state", {}).get("data", {}).get("data", {}).get("data", [])
            break

    results: list[Listing] = []
    for raw in items:
        listing = _parse_item(raw)
        if listing:
            results.append(listing)

    return results
