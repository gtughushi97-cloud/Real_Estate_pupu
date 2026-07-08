"""საერთო დამხმარე ფუნქციები ყველა სქრეპერისთვის."""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

TBILISI = ZoneInfo("Asia/Tbilisi")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ka,en;q=0.9",
}

@dataclass
class Listing:
    source: str          # მაგ. "ss.ge"
    url: str
    district: str
    price_usd: float | None
    area: float
    rooms: int | None
    floor: str | None
    posted_at: datetime  # tz-aware, Asia/Tbilisi


def compute_cutoff(run_type: str, now: datetime) -> datetime:
    """განსაზღვრავს დროის ზღვარს, რომლის შემდეგაც განთავსებული განცხადებები ჩაითვლება 'ახლად დამატებულად'."""
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if run_type == "morning":
        return today_midnight
    if run_type == "evening":
        return today_midnight + timedelta(hours=12)
    # ხელით გაშვება ან უცნობი ტიპი — ბოლო 7 საათი
    return now - timedelta(hours=7)


def sanity_check(listing: Listing) -> bool:
    """გამორიცხავს აშკარად არასწორ/არარელევანტურ ჩანაწერებს (მაგ. გაქირავების ან დაზიანებული მონაცემები)."""
    if listing.area is None or listing.area < 12 or listing.area > 1500:
        return False
    if listing.price_usd is not None and listing.price_usd < 2000:
        return False
    return True


def dedupe(listings: list[Listing]) -> list[Listing]:
    seen: set[str] = set()
    unique: list[Listing] = []
    for item in listings:
        if item.url in seen:
            continue
        seen.add(item.url)
        if sanity_check(item):
            unique.append(item)
    return unique


def dedupe_and_sort(listings: list[Listing]) -> list[Listing]:
    unique = dedupe(listings)
    unique.sort(key=lambda x: x.area)
    return unique


def format_price(price_usd: float | None) -> str:
    if price_usd is None:
        return "ფასი შეთანხმებით"
    return f"{price_usd:,.0f}$".replace(",", " ")


def price_per_sqm(listing: Listing) -> float | None:
    if listing.price_usd is None or listing.area <= 0:
        return None
    return listing.price_usd / listing.area


MIN_DISTRICT_SAMPLES = 3
MARKET_LOW_RATIO = 0.9
MARKET_HIGH_RATIO = 1.1


def compute_district_medians(listings: list[Listing], min_samples: int = MIN_DISTRICT_SAMPLES) -> dict[str, float]:
    """თითოეული რაიონისთვის ითვლის მ²-ის მედიანურ ფასს, სრული დასქროლილი
    ნიმუშის მიხედვით (არა მხოლოდ 'ახალი' განცხადებების), რომ საბაზრო
    შედარება საიმედო იყოს."""
    by_district: dict[str, list[float]] = {}
    for item in listings:
        psqm = price_per_sqm(item)
        if psqm is None:
            continue
        by_district.setdefault(item.district, []).append(psqm)

    return {
        district: statistics.median(values)
        for district, values in by_district.items()
        if len(values) >= min_samples
    }


def classify_market(listing: Listing, medians: dict[str, float]) -> tuple[str, str]:
    """აბრუნებს (ლეიბლი, css-კლასი) წყვილს — შედარებით რაიონის მედიანურ მ²-ფასთან."""
    median = medians.get(listing.district)
    psqm = price_per_sqm(listing)
    if median is None or psqm is None:
        return "მონაცემი არასაკმარისია", "unknown"

    ratio = psqm / median
    if ratio < MARKET_LOW_RATIO:
        return "დაბალი ფასი", "low"
    if ratio > MARKET_HIGH_RATIO:
        return "მაღალი ფასი", "high"
    return "საბაზრო ფასი", "market"


def fetch_with_retry(url: str, headers: dict | None = None, params: dict | None = None, retries: int = 2, timeout: int = 20) -> requests.Response:
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=merged_headers, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:  # noqa: PERF203
            last_exc = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise last_exc  # type: ignore[misc]
