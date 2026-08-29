#!/usr/bin/env python3
"""VF1-WP1: fetch public PAGE TEXT only. Do not follow game embeds.

Clean-room: observe listing/developer/wiki HTML. Do not download SWF,
Flash, HTML5 game packages, sprites, audio, or title-card images.
"""

from __future__ import annotations

import hashlib
import json
import re
import ssl
import sys
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SAIGON = timezone(timedelta(hours=7), name="Asia/Saigon")
HERE = Path(__file__).resolve().parent
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36 HH-VF1-WP1-page-text/1"
)

# Public pages only. Embed/CDN game URLs are recorded, never fetched.
PAGES = [
    {
        "id": "y8_listing",
        "url": "https://www.y8.com/games/superfighters",
        "role": "primary_public_listing",
        "kind": "primary",
    },
    {
        "id": "newgrounds_listing",
        "url": "https://www.newgrounds.com/portal/view/575163",
        "role": "original_release_listing",
        "kind": "primary",
    },
    {
        "id": "mythologic_superfighters",
        "url": "https://mythologicinteractive.com/Superfighters",
        "role": "developer_controls_crosscheck",
        "kind": "primary",
    },
    {
        "id": "mythologic_superfighters_www",
        "url": "https://www.mythologicinteractive.com/Superfighters",
        "role": "developer_controls_crosscheck_www",
        "kind": "primary",
    },
    {
        "id": "mythologic_home",
        "url": "https://www.mythologicinteractive.com/",
        "role": "developer_home_for_live_link",
        "kind": "primary",
    },
    {
        "id": "wiki_game",
        "url": "https://mythologicinteractivesuperfighters.fandom.com/wiki/Superfighters",
        "role": "community_secondary_overview",
        "kind": "secondary",
    },
    {
        "id": "wiki_maps",
        "url": "https://mythologicinteractivesuperfighters.fandom.com/wiki/Maps",
        "role": "community_secondary_maps",
        "kind": "secondary",
    },
    {
        "id": "wiki_game_modes",
        "url": "https://mythologicinteractivesuperfighters.fandom.com/wiki/Game_Modes",
        "role": "community_secondary_modes",
        "kind": "secondary",
    },
    {
        "id": "wiki_combat",
        "url": "https://mythologicinteractivesuperfighters.fandom.com/wiki/Combat_Techniques",
        "role": "community_secondary_movement",
        "kind": "secondary",
    },
    {
        "id": "wayback_mythologic",
        "url": "https://web.archive.org/web/2020/https://mythologicinteractive.com/Superfighters",
        "role": "historical_developer_page_if_live_404",
        "kind": "secondary",
    },
]

EMBED_HINTS = (
    "swf",
    ".unity3d",
    "ruffle",
    "html5game",
    "gameframe",
    "/games/embed",
    "uploads/games",
    "ungrounded.net",
    "newgrounds.com/portal/video",
    "y8.com/games/embed",
    "cloudflare",
    "cdn",
)


class PageExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self.texts: list[str] = []
        self.attrs_text: list[str] = []
        self.iframes: list[str] = []
        self.scripts_src: list[str] = []
        self.embeds: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k.lower(): (v or "") for k, v in attrs}
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag == "iframe":
            src = ad.get("src") or ad.get("data-src") or ""
            if src:
                self.iframes.append(src)
        if tag == "script" and ad.get("src"):
            self.scripts_src.append(ad["src"])
        if tag in {"embed", "object", "source"}:
            src = ad.get("src") or ad.get("data") or ""
            if src:
                self.embeds.append(src)
        for key in (
            "alt",
            "aria-label",
            "title",
            "data-key",
            "data-control",
            "data-action",
            "placeholder",
        ):
            val = ad.get(key)
            if val and val.strip():
                self.attrs_text.append(f"{tag}@{key}={val.strip()}")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip > 0:
            self._skip -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        chunk = " ".join(data.split())
        if not chunk:
            return
        if self._in_title:
            self.title = chunk
        self.texts.append(chunk)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def looks_like_game_package(url: str) -> bool:
    low = url.lower()
    if any(low.endswith(ext) for ext in (".swf", ".unity3d", ".pak", ".zip", ".7z")):
        return True
    return False


def fetch(url: str, timeout: int = 35) -> dict:
    started = datetime.now(SAIGON).isoformat(timespec="seconds")
    req = Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})
    ctx = ssl.create_default_context()
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
            info = {
                "ok": True,
                "http_status": int(getattr(resp, "status", 200) or 200),
                "final_url": str(resp.geturl()),
                "content_type": str(resp.headers.get("Content-Type") or ""),
                "bytes": len(raw),
                "error": "",
            }
    except HTTPError as exc:
        raw = exc.read() if exc.fp is not None else b""
        info = {
            "ok": False,
            "http_status": int(exc.code),
            "final_url": url,
            "content_type": str(exc.headers.get("Content-Type") if exc.headers else ""),
            "bytes": len(raw),
            "error": f"HTTPError {exc.code}",
        }
    except (URLError, TimeoutError, ssl.SSLError, OSError) as exc:
        raw = b""
        info = {
            "ok": False,
            "http_status": 0,
            "final_url": url,
            "content_type": "",
            "bytes": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }
    info["fetched_at_asia_saigon"] = started
    info["finished_at_asia_saigon"] = datetime.now(SAIGON).isoformat(timespec="seconds")
    info["raw_sha256"] = sha256_bytes(raw) if raw else ""
    return info, raw


def extract(html: bytes) -> dict:
    parser = PageExtractor()
    try:
        parser.feed(html.decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001 — record parse failure honestly
        return {
            "title": "",
            "text": f"[parse_error] {exc}",
            "attr_notes": [],
            "iframes": [],
            "embeds": [],
            "script_srcs": [],
        }
    text = "\n".join(parser.texts)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return {
        "title": parser.title,
        "text": text,
        "attr_notes": parser.attrs_text[:400],
        "iframes": parser.iframes,
        "embeds": parser.embeds,
        "script_srcs": parser.scripts_src[:80],
    }


def main() -> int:
    HERE.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    for page in PAGES:
        info, raw = fetch(page["url"])
        rec = {
            **page,
            **info,
            "game_package_fetched": False,
            "embed_urls_not_fetched": [],
        }
        if raw and "html" not in (info.get("content_type") or "").lower() and raw[:1] not in (b"<", b"\xef"):
            rec["note"] = "non-html body skipped; not saved"
            rec["text_sha256"] = ""
            rec["text_path"] = ""
        else:
            extracted = extract(raw) if raw else {
                "title": "",
                "text": "",
                "attr_notes": [],
                "iframes": [],
                "embeds": [],
                "script_srcs": [],
            }
            embeds = list(extracted["iframes"]) + list(extracted["embeds"])
            rec["embed_urls_not_fetched"] = embeds
            rec["script_src_count"] = len(extracted["script_srcs"])
            rec["page_title"] = extracted["title"]
            rec["game_package_urls_seen_not_fetched"] = [
                u for u in embeds if looks_like_game_package(u)
            ]
            text = extracted["text"]
            # Keep a bounded control-relevant attribute dump, not images.
            attr_block = "\n".join(extracted["attr_notes"])
            transcript = (
                f"URL: {page['url']}\n"
                f"FINAL: {info.get('final_url')}\n"
                f"STATUS: {info.get('http_status')}\n"
                f"FETCHED_AT: {info.get('fetched_at_asia_saigon')}\n"
                f"TITLE: {extracted['title']}\n"
                f"EMBED_URLS_NOT_FETCHED: {json.dumps(embeds, ensure_ascii=True)}\n"
                f"\n===== VISIBLE TEXT =====\n{text}\n"
                f"\n===== ATTR NOTES (alt/aria/title/data-*) =====\n{attr_block}\n"
            )
            name = f"{page['id']}.transcript.txt"
            path = HERE / name
            path.write_text(transcript, encoding="utf-8", newline="\n")
            rec["text_path"] = name
            rec["text_sha256"] = sha256_text(transcript)
            rec["text_bytes"] = len(transcript.encode("utf-8"))
        records.append(rec)
        print(f"{page['id']}\t{info.get('http_status')}\t{info.get('error') or 'ok'}\t{info.get('bytes')}")

    manifest = {
        "schema": "vault-fighters.vf1-wp1.page-fetch.v1",
        "run_id": "VF1WP1-20260829-ASIA-SAIGON-01",
        "command_id": "cmd.vf1-wp1.fetch-public-pages.1",
        "timezone": "Asia/Saigon",
        "recorded_at": datetime.now(SAIGON).isoformat(timespec="seconds"),
        "clean_room": {
            "game_package_downloaded": False,
            "screenshots_saved": False,
            "swf_html5_ripped": False,
        },
        "pages": records,
    }
    man_path = HERE / "page_fetch.manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {man_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
