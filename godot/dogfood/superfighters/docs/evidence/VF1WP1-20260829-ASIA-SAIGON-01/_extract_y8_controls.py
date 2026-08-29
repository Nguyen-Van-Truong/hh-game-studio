#!/usr/bin/env python3
"""Re-fetch Y8 listing HTML; save controls snippet only. No game package."""

from __future__ import annotations

import json
import re
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

SAIGON = timezone(timedelta(hours=7), name="Asia/Saigon")
HERE = Path(__file__).resolve().parent
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36 HH-VF1-WP1-page-text/1"
)
URL = "https://www.y8.com/games/superfighters"


def main() -> int:
    req = Request(URL, headers={"User-Agent": UA, "Accept": "text/html"})
    ctx = ssl.create_default_context()
    with urlopen(req, timeout=40, context=ctx) as resp:
        raw = resp.read()
        status = int(resp.status)
        ctype = str(resp.headers.get("Content-Type") or "")
    html = raw.decode("utf-8", errors="replace")
    now = datetime.now(SAIGON).isoformat(timespec="seconds")
    needles = [
        "Game controls",
        "Player 1",
        "Player 2",
        "walkthrough",
        "iframe",
        "html5",
        "embed",
        "Arrow",
        "WASD",
        "comma",
        "grenade",
        "punch",
        "shoot",
        "keyboard",
    ]
    counts = {n: html.lower().count(n.lower()) for n in needles}
    iframes = re.findall(r"<(?:iframe|embed|source)[^>]+>", html, flags=re.I)
    urls = re.findall(r"https?://[^\"'\s>]+", html)
    interesting = [
        u
        for u in urls
        if re.search(r"(embed|game|swf|html5|ruffle|walkthrough|superfight)", u, re.I)
    ]
    idx = html.lower().find("game controls")
    snippet = html[max(0, idx - 200) : idx + 4000] if idx >= 0 else ""
    snippet_path = HERE / "y8_controls_html_snippet.txt"
    header = (
        f"FETCHED_AT={now}\nSTATUS={status}\nBYTES={len(raw)}\n"
        f"CONTENT_TYPE={ctype}\nNOTE=controls window only; full HTML not saved\n\n"
    )
    snippet_path.write_text(header + snippet, encoding="utf-8", newline="\n")
    report = {
        "fetched_at_asia_saigon": now,
        "http_status": status,
        "bytes": len(raw),
        "content_type": ctype,
        "counts": counts,
        "iframe_tag_count": len(iframes),
        "iframe_tags_sample": iframes[:12],
        "interesting_url_count": len(interesting),
        "interesting_urls_sample": interesting[:40],
        "controls_marker_index": idx,
        "snippet_path": snippet_path.name,
        "snippet_chars": len(snippet),
        "game_package_fetched": False,
    }
    out = HERE / "y8_controls_extract.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "bytes": len(raw), "idx": idx, "iframes": len(iframes)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
