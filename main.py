"""ბინების მონიტორინგის მთავარი სკრიპტი.

უშვებს სამივე სქრეპერს (ss.ge, myhome.ge, korter.ge), აერთიანებს
შედეგებს, ფილტრავს განთავსების დროის მიხედვით და აწყობს ერთ სტატიკურ
HTML გვერდს (docs/index.html), ფართობის ზრდადობით დალაგებულს.
გვერდს აქვეყნებს GitHub Pages.

გაშვება დღეში სამჯერ (00:00, 12:00, 19:00, თბილისის დროით) GitHub
Actions-ის cron-ით — იხილეთ .github/workflows/scrape.yml.
00:00-ის გაშვება უბრალოდ ასუფთავებს გვერდს (წინა დღის მონაცემები არ
ინახება), ხოლო 12:00 და 19:00 რეალურად სქრეპავს საიტებს.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scraper import korter_ge, myhome_ge, ss_ge
from scraper.common import TBILISI, compute_cutoff, compute_district_medians, dedupe
from scraper.myhome_ge import MyHomeBlockedError
from scraper.render import render_page

OUTPUT_PATH = Path(__file__).parent / "docs" / "index.html"


def run(run_type: str) -> int:
    now = datetime.now(TBILISI)
    print(f"[{now.isoformat()}] გაშვების ტიპი: {run_type}")

    if run_type == "midnight":
        html = render_page([], {}, run_type, now, now, {})
        OUTPUT_PATH.parent.mkdir(exist_ok=True)
        OUTPUT_PATH.write_text(html, encoding="utf-8")
        print("გვერდი გასუფთავდა 00:00-ის გაშვებაზე.")
        return 0

    cutoff = compute_cutoff(run_type, now)
    print(f"ზღვარი: {cutoff.isoformat()}")

    all_scanned = []
    source_errors: dict[str, str] = {}

    for name, fetch_fn in (
        ("ss.ge", lambda: ss_ge.fetch_listings()),
        ("myhome.ge", lambda: myhome_ge.fetch_listings()),
        ("korter.ge", lambda: korter_ge.fetch_listings()),
    ):
        try:
            found = fetch_fn()
            print(f"  {name}: სულ დასქროლილი {len(found)}")
            all_scanned.extend(found)
        except MyHomeBlockedError as exc:
            print(f"  {name}: დაბლოკილია — {exc}")
            source_errors[name] = str(exc)
        except Exception as exc:  # noqa: BLE001
            print(f"  {name}: შეცდომა — {exc}")
            source_errors[name] = "დროებითი შეცდომა"

    all_scanned = dedupe(all_scanned)
    medians = compute_district_medians(all_scanned)
    print(f"საბაზრო მედიანა გამოთვლილია {len(medians)} რაიონისთვის ({len(all_scanned)} განცხადებიდან)")

    new_listings = [item for item in all_scanned if item.posted_at >= cutoff]
    new_listings.sort(key=lambda x: x.area)
    print(f"ახალი განცხადება (ზღვრის შემდეგ): {len(new_listings)}")

    html = render_page(new_listings, medians, run_type, cutoff, now, source_errors)
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"გვერდი განახლდა: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    run_type_arg = sys.argv[1] if len(sys.argv) > 1 else "manual"
    sys.exit(run(run_type_arg))
