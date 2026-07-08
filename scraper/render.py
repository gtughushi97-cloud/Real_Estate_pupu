"""დინამიური HTML გვერდის აწყობა ბოლო გაშვების შედეგებით."""

from __future__ import annotations

from datetime import datetime
from html import escape

from .common import Listing, classify_market, format_price, price_per_sqm

RUN_LABELS = {
    "morning": "დღის განახლება (12:00)",
    "evening": "საღამოს განახლება (19:00)",
    "midnight": "დღის დასაწყისი (00:00) — გასუფთავებულია",
    "manual": "სატესტო/ხელით გაშვება",
}

MARKET_LABELS = {
    "low": "📉 დაბალი ფასი",
    "market": "საბაზრო ფასი",
    "high": "📈 მაღალი ფასი",
    "unknown": "მონაცემი არასაკმარისია",
}

PAGE_TEMPLATE = """<!doctype html>
<html lang="ka">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
<title>ბინების მონიტორინგი</title>
<style>
  :root {{
    color-scheme: light dark;
    --bg: #f6f5f2;
    --card: #ffffff;
    --text: #1f2532;
    --muted: #667085;
    --accent: #16233d;
    --accent2: #c9a24c;
    --border: #e6e2da;
    --low: #1a7f4b;
    --low-bg: #e5f5ec;
    --high: #b3391f;
    --high-bg: #fbe9e5;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0f1420;
      --card: #171d2b;
      --text: #eef0f4;
      --muted: #9aa4b8;
      --accent: #dfe6f5;
      --accent2: #d8b567;
      --border: #2a3346;
      --low: #4ade80;
      --low-bg: #123023;
      --high: #f87171;
      --high-bg: #331616;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, "Segoe UI", Roboto, "Noto Sans Georgian", sans-serif;
    background: var(--bg);
    color: var(--text);
  }}
  header {{
    padding: 28px 20px 20px;
    max-width: 960px;
    margin: 0 auto;
  }}
  header h1 {{
    margin: 0 0 6px;
    font-size: 24px;
  }}
  .meta {{
    color: var(--muted);
    font-size: 14px;
    line-height: 1.6;
  }}
  .badge {{
    display: inline-block;
    background: var(--accent2);
    color: var(--accent);
    font-weight: 700;
    font-size: 12px;
    padding: 3px 10px;
    border-radius: 999px;
    margin-inline-start: 6px;
  }}
  .warning {{
    max-width: 960px;
    margin: 0 auto 16px;
    padding: 12px 16px;
    background: #fff3cd;
    color: #664d03;
    border-radius: 10px;
    font-size: 14px;
  }}
  main {{
    max-width: 960px;
    margin: 0 auto;
    padding: 0 20px 60px;
  }}
  .filters {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 10px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 20px;
  }}
  .filters label {{
    display: block;
    font-size: 11px;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin-bottom: 5px;
  }}
  .filters select,
  .filters input {{
    width: 100%;
    font-family: inherit;
    font-size: 14px;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--text);
  }}
  .filters .reset-wrap {{
    display: flex;
    align-items: end;
  }}
  .filters button {{
    width: 100%;
    padding: 9px 10px;
    border-radius: 8px;
    border: none;
    background: var(--accent);
    color: var(--bg);
    font-weight: 700;
    font-size: 13px;
    cursor: pointer;
  }}
  .empty {{
    text-align: center;
    padding: 60px 20px;
    color: var(--muted);
  }}
  .count {{
    font-size: 14px;
    color: var(--muted);
    margin-bottom: 16px;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 16px;
  }}
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    text-decoration: none;
    color: var(--text);
    transition: transform 120ms ease, box-shadow 120ms ease;
  }}
  .card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.12);
  }}
  .card .top-row {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
  }}
  .card .area {{
    font-size: 20px;
    font-weight: 800;
  }}
  .card .district {{
    font-size: 14px;
    color: var(--muted);
  }}
  .card .price {{
    font-size: 16px;
    font-weight: 700;
    color: var(--accent2);
  }}
  .card .psqm {{
    font-size: 12px;
    color: var(--muted);
  }}
  .market-tag {{
    font-size: 11px;
    font-weight: 700;
    padding: 3px 9px;
    border-radius: 999px;
    white-space: nowrap;
    background: var(--border);
    color: var(--muted);
  }}
  .market-tag.low {{ background: var(--low-bg); color: var(--low); }}
  .market-tag.high {{ background: var(--high-bg); color: var(--high); }}
  .card .details {{
    font-size: 13px;
    color: var(--muted);
    display: flex;
    justify-content: space-between;
    border-top: 1px solid var(--border);
    padding-top: 8px;
    margin-top: 4px;
  }}
  footer {{
    text-align: center;
    color: var(--muted);
    font-size: 12px;
    padding: 20px;
  }}
</style>
</head>
<body>
<header>
  <h1>🏠 ბინების მონიტორინგი</h1>
  <div class="meta">
    ბოლო განახლება: <strong>{updated_at}</strong>
    <span class="badge">{run_label}</span><br />
    წყაროები: ss.ge, myhome.ge, korter.ge (თბილისი) · ახალი განცხადებები {cutoff}-დან<br />
    ავტომატურად განახლდება 00:00-ზე (გასუფთავება), 12:00-სა და 19:00-ზე
  </div>
</header>
{warning_block}
<main>
{filters_block}
{body}
</main>
<footer>დემო/პირადი გამოყენებისთვის · მონაცემები არ ინახება წინა დღეებიდან · ფასი საბაზროსთან შედარებულია რაიონის მედიანურ მ²-ფასთან</footer>
<script>
(function() {{
  var districtSel = document.getElementById('f-district');
  var areaMin = document.getElementById('f-area-min');
  var areaMax = document.getElementById('f-area-max');
  var priceMin = document.getElementById('f-price-min');
  var priceMax = document.getElementById('f-price-max');
  var resetBtn = document.getElementById('f-reset');
  var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));
  var countEl = document.getElementById('visible-count');

  function apply() {{
    var district = districtSel ? districtSel.value : '';
    var aMin = parseFloat(areaMin.value) || 0;
    var aMax = parseFloat(areaMax.value) || Infinity;
    var pMin = parseFloat(priceMin.value) || 0;
    var pMax = parseFloat(priceMax.value) || Infinity;
    var visible = 0;

    cards.forEach(function(card) {{
      var d = card.dataset.district;
      var a = parseFloat(card.dataset.area);
      var p = card.dataset.price ? parseFloat(card.dataset.price) : null;
      var ok = true;
      if (district && d !== district) ok = false;
      if (a < aMin || a > aMax) ok = false;
      if (p !== null && (p < pMin || p > pMax)) ok = false;
      card.style.display = ok ? '' : 'none';
      if (ok) visible++;
    }});
    if (countEl) countEl.textContent = visible;
  }}

  [districtSel, areaMin, areaMax, priceMin, priceMax].forEach(function(el) {{
    if (el) el.addEventListener('input', apply);
  }});
  if (resetBtn) {{
    resetBtn.addEventListener('click', function() {{
      if (districtSel) districtSel.value = '';
      areaMin.value = ''; areaMax.value = '';
      priceMin.value = ''; priceMax.value = '';
      apply();
    }});
  }}
}})();
</script>
</body>
</html>
"""

CARD_TEMPLATE = """<a class="card" href="{url}" target="_blank" rel="noopener" data-district="{district_attr}" data-area="{area_attr}" data-price="{price_attr}">
  <div class="top-row">
    <div class="area">{area:g} მ²</div>
    <span class="market-tag {market_class}">{market_label}</span>
  </div>
  <div class="district">📍 {district}</div>
  <div class="price">{price}</div>
  <div class="psqm">{psqm}</div>
  <div class="details"><span>{rooms}{floor}</span><span>{source}</span></div>
</a>"""

FILTERS_TEMPLATE = """<div class="filters">
  <div>
    <label for="f-district">რაიონი</label>
    <select id="f-district">
      <option value="">ყველა</option>
      {district_options}
    </select>
  </div>
  <div>
    <label for="f-area-min">ფართობი, დან (მ²)</label>
    <input id="f-area-min" type="number" min="0" placeholder="0" />
  </div>
  <div>
    <label for="f-area-max">ფართობი, მდე (მ²)</label>
    <input id="f-area-max" type="number" min="0" placeholder="500" />
  </div>
  <div>
    <label for="f-price-min">ფასი, დან ($)</label>
    <input id="f-price-min" type="number" min="0" placeholder="0" />
  </div>
  <div>
    <label for="f-price-max">ფასი, მდე ($)</label>
    <input id="f-price-max" type="number" min="0" placeholder="500000" />
  </div>
  <div class="reset-wrap">
    <button id="f-reset" type="button">გასუფთავება</button>
  </div>
</div>"""


def render_page(
    listings: list[Listing],
    medians: dict[str, float],
    run_type: str,
    cutoff: datetime,
    now: datetime,
    source_errors: dict[str, str],
) -> str:
    run_label = RUN_LABELS.get(run_type, run_type)

    warning_block = ""
    if source_errors:
        failed = ", ".join(f"{name} ({reason})" for name, reason in source_errors.items())
        warning_block = f'<div class="warning">⚠️ ვერ დამუშავდა: {escape(failed)}</div>'

    if not listings:
        filters_block = ""
        body = '<div class="empty">ახალი განცხადება ვერ მოიძებნა.</div>'
    else:
        districts = sorted({item.district for item in listings})
        district_options = "\n".join(
            f'<option value="{escape(d)}">{escape(d)}</option>' for d in districts
        )
        filters_block = FILTERS_TEMPLATE.format(district_options=district_options)

        cards = []
        for listing in listings:
            rooms = f"{listing.rooms} ოთახი" if listing.rooms else "ოთახები N/A"
            floor = f" · {listing.floor} სართ." if listing.floor else ""
            market_label, market_class = classify_market(listing, medians)
            psqm = price_per_sqm(listing)
            psqm_text = f"≈ {psqm:,.0f}$ / მ²".replace(",", " ") if psqm else ""

            cards.append(
                CARD_TEMPLATE.format(
                    url=escape(listing.url),
                    district_attr=escape(listing.district),
                    area_attr=listing.area,
                    price_attr=listing.price_usd if listing.price_usd is not None else "",
                    area=listing.area,
                    district=escape(listing.district),
                    price=escape(format_price(listing.price_usd)),
                    psqm=escape(psqm_text),
                    market_class=market_class,
                    market_label=escape(MARKET_LABELS.get(market_class, market_label)),
                    rooms=escape(rooms),
                    floor=escape(floor),
                    source=escape(listing.source),
                )
            )
        body = (
            f'<div class="count">სულ <span id="visible-count">{len(listings)}</span> '
            f'/ {len(listings)} განცხადება, დალაგებულია ფართობის ზრდადობით</div>'
        )
        body += f'<div class="grid">{"".join(cards)}</div>'

    return PAGE_TEMPLATE.format(
        updated_at=now.strftime("%Y-%m-%d %H:%M"),
        run_label=escape(run_label),
        cutoff=cutoff.strftime("%H:%M"),
        warning_block=warning_block,
        filters_block=filters_block,
        body=body,
    )
