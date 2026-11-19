"""Trend radar: recent off-road videos on YouTube ranked by views per hour.

Several queries (Polish and English by default) are merged and de-duplicated. Shorts and live streams
are skipped, and videos shorter than --min-minutes are dropped, because long videos are the ones
worth clipping. Videos under a Creative Commons licence are marked: those allow reuse with credit.

usage: python trends.py [--query "offroad 4x4" --query "off road polska"] [--hours 72] [--limit 25]
                        [--min-minutes 4] [--out trends.md]
"""
import argparse, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote_plus
sys.path.insert(0, str(Path(__file__).parent))
from common import ytdlp_json

UPLOAD_DATE_SORT = "&sp=CAI%253D"  # YouTube search sorted by upload date
DEFAULT_QUERIES = ["offroad 4x4", "off road polska", "offroad mud", "terenówki błoto", "overlanding"]


ERRORS = []


def detail(url):
    try:
        return ytdlp_json(url, ["--skip-download"])
    except SystemExit as e:
        ERRORS.append(str(e))
        return None


def search(q, limit):
    try:
        flat = ytdlp_json(f"https://www.youtube.com/results?search_query={quote_plus(q)}{UPLOAD_DATE_SORT}",
                          ["--flat-playlist", "--playlist-end", str(limit)])
    except SystemExit as e:
        print(f"search failed for {q!r}: {str(e)[-200:]}", file=sys.stderr)
        return []
    return [e["url"] for e in flat.get("entries", []) if e.get("url") and "/shorts/" not in e["url"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", action="append", help="repeatable; default: Polish + English off-road queries")
    ap.add_argument("--hours", type=float, default=72); ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--min-minutes", type=float, default=4); ap.add_argument("--out", default="trends.md")
    a = ap.parse_args()
    queries = a.query or DEFAULT_QUERIES
    urls = []
    for q in queries:
        for u in search(q, a.limit):
            if u not in urls:
                urls.append(u)
    if not urls:
        sys.exit("no search results (network, or yt-dlp too old: pip install -U yt-dlp)")
    with ThreadPoolExecutor(6) as ex:
        infos = [i for i in ex.map(detail, urls) if i]
    now = time.time(); rows = []
    for i in infos:
        t = i.get("timestamp") or i.get("release_timestamp")
        if not t or i.get("is_live") or (i.get("duration") or 0) < a.min_minutes * 60:
            continue
        age = max(0.25, (now - t) / 3600)
        if age > a.hours:
            continue
        v = i.get("view_count") or 0
        cc = "creative commons" in (i.get("license") or "").lower()
        rows.append((v / age, v, age, i.get("duration") or 0, i.get("channel") or "", i.get("title") or "",
                     i.get("webpage_url"), bool(i.get("heatmap")), cc))
    rows.sort(reverse=True)
    md = [f"# Trendy offroad, ostatnie {a.hours:.0f} h ({time.strftime('%d.%m.%Y %H:%M UTC', time.gmtime())})",
          f"zapytania: {', '.join(queries)}", "",
          "| # | wyśw./h | wyśw. | wiek h | min | kanał | tytuł | najczęściej odtw. | CC |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k, r in enumerate(rows, 1):
        md.append(f"| {k} | {r[0]:,.0f} | {r[1]:,} | {r[2]:.0f} | {r[3] / 60:.0f} | {r[4]} | [{r[5][:70]}]({r[6]}) | "
                  f"{'tak' if r[7] else ''} | {'CC BY' if r[8] else ''} |")
    Path(a.out).write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:15]))
    print(f"... {len(rows)} videos -> {a.out}")
    if ERRORS:
        bot = any("not a bot" in e for e in ERRORS)
        print(f"warning: {len(ERRORS)} of {len(urls)} videos could not be read"
              + (". YouTube asks for sign-in: set YTDLP_BROWSER=chrome (or firefox/edge) to use your browser cookies."
                 if bot else f": {ERRORS[0][-200:]}"), file=sys.stderr)


if __name__ == "__main__":
    main()
