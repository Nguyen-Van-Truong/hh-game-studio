"""hh asset: copy a file into a Godot project with a license ledger, media checks, and credits.

``asset add`` validates the request on the host (path, license, media), dedupes ``command_id``
through the project journal, checkpoints the dest and the ledger, writes both by temp-file
replace, runs the editor import pass, and acknowledges only after the ledger sha and, for
importable types, the Godot ``.import`` sidecar match. ``asset credits`` writes ``CREDITS.md``
with the same journal contract.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from . import common as C
from . import media_inspect as M
from . import scene

LICENSES_PATH = C.GAMEKIT_DIR / "licenses.json"
LEDGER_RES = "res://hh_assets.json"
LEDGER_SCHEMA = "hh-gamekit-assets-1"
ALLOWED_EXTS = {
    ".png", ".jpg", ".jpeg", ".webp", ".svg", ".glb", ".gltf", ".wav", ".ogg", ".mp3",
    ".ttf", ".otf", ".woff2", ".json", ".txt",
}
# Godot writes a sibling ``.import`` for these. JSON and plain text are copied as data files.
IMPORTABLE_EXTS = ALLOWED_EXTS - {".json", ".txt"}
MAX_ASSET_BYTES = 128 * 1024 * 1024
_URL_OK = ("https://", "http://")


def load_licenses() -> dict[str, Any]:
    data = C.read_json(LICENSES_PATH)
    if not isinstance(data, dict) or data.get("schema") != "hh-gamekit-licenses-1":
        raise C.GamekitError("STATE_CORRUPT", "licenses.json schema mismatch")
    if (not isinstance(data.get("allowed"), list) or not isinstance(data.get("reject_rules"), list)
            or not isinstance(data.get("owner_review", []), list)):
        raise C.GamekitError("STATE_CORRUPT", "licenses.json is malformed")
    return data


def _rejection_reason(license_id: str, table: dict[str, Any]) -> str:
    upper = license_id.upper()
    folded = license_id.casefold()
    for rec in table.get("owner_review", []):
        if isinstance(rec, dict) and str(rec.get("id", "")).casefold() == folded:
            return (f"{license_id} is free but not allowed yet: owner rule 09-10 (budget 0) ships only CC0-1.0 or "
                    "self-made; the owner decides (E3) by moving it into allowed in studio/gamekit/licenses.json")
    for rule in table["reject_rules"]:
        if not isinstance(rule, dict):
            continue
        op = rule.get("op")
        if op == "contains" and str(rule.get("value", "")).upper() in upper:
            return str(rule.get("reason") or "license rejected")
        if op == "equals" and folded == str(rule.get("value", "")).casefold():
            return str(rule.get("reason") or "license rejected")
        if op == "contains_any":
            values = rule.get("value") or []
            if any(str(item).upper() in upper for item in values):
                return str(rule.get("reason") or "license rejected")
        if op == "prefix" and upper.startswith(str(rule.get("value", "")).upper()):
            return str(rule.get("reason") or "license rejected")
    return "license id is not allowed"


def check_license(license_id: str, author: str = "") -> dict[str, Any]:
    """Return the allow-list record or raise ``LICENSE_REJECTED`` / ``VALIDATION_FAILED``."""
    if not isinstance(license_id, str) or not license_id.strip():
        raise C.GamekitError("LICENSE_REJECTED", "license id is empty")
    table = load_licenses()
    author_text = author.strip() if isinstance(author, str) else ""
    for rec in table["allowed"]:
        if isinstance(rec, dict) and rec.get("id") == license_id:
            if rec.get("requires_author") and not author_text:
                raise C.GamekitError("VALIDATION_FAILED", "self-made requires --author")
            return rec
    raise C.GamekitError("LICENSE_REJECTED", _rejection_reason(license_id.strip(), table))


def _clean_author(author: str) -> str:
    if not isinstance(author, str):
        raise C.GamekitError("VALIDATION_FAILED", "author is required")
    text = author.strip()
    if not text or len(text) > 200 or any(ord(ch) < 32 for ch in text):
        raise C.GamekitError("VALIDATION_FAILED", "author must be 1..200 characters without control characters")
    return text


def _clean_notes(notes: str | None) -> str:
    if notes is None:
        return ""
    if not isinstance(notes, str):
        raise C.GamekitError("VALIDATION_FAILED", "notes must be a string")
    text = notes.strip()
    if len(text) > 500 or any(ord(ch) < 32 for ch in text):
        raise C.GamekitError("VALIDATION_FAILED", "notes must be at most 500 characters without control characters")
    return text


def _clean_url(source_url: str | None) -> str:
    if source_url is None or source_url == "":
        return ""
    if not isinstance(source_url, str) or len(source_url) > 300 or any(ord(ch) < 33 for ch in source_url):
        raise C.GamekitError("VALIDATION_FAILED", "source-url must be an http(s) URL")
    if not source_url.startswith(_URL_OK):
        raise C.GamekitError("VALIDATION_FAILED", "source-url must start with http:// or https://")
    return source_url


def _require_bool(value: bool, name: str) -> bool:
    if not isinstance(value, bool):
        raise C.GamekitError("VALIDATION_FAILED", f"{name} must be a boolean")
    return value


def _refuse_source(source: Path) -> Path:
    """Refuse a junction, symlink, ``private.raw``, or ``studio/.local`` source. Returns the resolved path."""
    return C.refuse_unsafe_host_path(Path(source), what="asset source")


def _dest_pair(project: C.Project, dest: str) -> tuple[str, Path]:
    path = project.res_to_path(dest)
    res = project.path_to_res(path)
    if res == LEDGER_RES:
        raise C.GamekitError("VALIDATION_FAILED", "dest collides with the asset ledger")
    ext = path.suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise C.GamekitError("VALIDATION_FAILED", f"extension {ext or '(none)'} is not in the asset allow list")
    return res, path


def _load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": LEDGER_SCHEMA, "assets": []}
    data = C.read_json(path)
    if not isinstance(data, dict) or data.get("schema") != LEDGER_SCHEMA or not isinstance(data.get("assets"), list):
        raise C.GamekitError("STATE_CORRUPT", "asset ledger is malformed")
    seen: set[str] = set()
    assets = []
    for entry in data["assets"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("res"), str):
            raise C.GamekitError("STATE_CORRUPT", "asset ledger entry is malformed")
        if entry["res"] in seen:
            raise C.GamekitError("STATE_CORRUPT", f"asset ledger has a duplicate res {entry['res']}")
        seen.add(entry["res"])
        assets.append(entry)
    return {"schema": LEDGER_SCHEMA, "assets": assets}


def _with_entry(ledger: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    assets = []
    placed = False
    for old in ledger["assets"]:
        if old.get("res") == entry["res"]:
            if not placed:
                assets.append(entry)
                placed = True
        else:
            assets.append(old)
    if not placed:
        assets.append(entry)
    return {"schema": LEDGER_SCHEMA, "assets": assets}


def _import_brief(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "imported": True,
        "exit_code": result.get("exit_code"),
        "seconds": result.get("seconds"),
        "timed_out": bool(result.get("timed_out", False)),
        "error_count": len(result.get("errors") or []),
        "warning_count": len(result.get("warnings") or []),
    }


def _restore_or_raise(project: C.Project, command_id: str) -> None:
    try:
        C.restore_checkpoint(project, command_id)
    except Exception as exc:
        raise C.GamekitError("STATE_CORRUPT", f"checkpoint restore failed: {exc}") from exc


def _readback_add(project: C.Project, dest_path: Path, dest_res: str, sha: str, size: int, importable: bool) -> list[str]:
    problems = []
    if not dest_path.is_file():
        problems.append("dest missing after write")
        return problems
    if C.sha256_file(dest_path) != sha:
        problems.append("dest sha256 does not match the bytes that were written")
    if dest_path.stat().st_size != size:
        problems.append("dest byte size does not match")
    ledger_path = project.res_to_path(LEDGER_RES)
    try:
        ledger = _load_ledger(ledger_path)
    except C.GamekitError as exc:
        problems.append(f"ledger readback failed: {exc.detail}")
        return problems
    matches = [a for a in ledger["assets"] if a.get("res") == dest_res]
    if len(matches) != 1:
        problems.append("ledger entry missing after write")
    elif matches[0].get("sha256") != sha or matches[0].get("bytes") != size:
        problems.append("ledger sha256 does not match the dest file")
    if importable:
        sidecar = Path(str(dest_path) + ".import")
        if not sidecar.is_file() or sidecar.stat().st_size <= 0:
            problems.append("Godot .import sidecar is missing")
    return problems


def add(
    project: C.Project,
    source: str | Path,
    dest: str,
    license_id: str,
    author: str,
    *,
    command_id: str,
    source_url: str = "",
    ai_generated: bool = False,
    notes: str = "",
    replace: bool = False,
    allow_open_editor: bool = False,
) -> dict[str, Any]:
    """Copy ``source`` to ``dest`` and append or replace its ledger row."""
    command_id = C.validate_command_id(command_id)
    dest_res, dest_path = _dest_pair(project, dest)
    author = _clean_author(author)
    source_url = _clean_url(source_url)
    notes = _clean_notes(notes)
    ai_generated = _require_bool(ai_generated, "ai_generated")
    replace = _require_bool(replace, "replace")
    allow_open_editor = _require_bool(allow_open_editor, "allow_open_editor")
    src = _refuse_source(Path(source))
    if not src.exists():
        raise C.GamekitError("NOT_FOUND", f"source file not found: {src}")
    if not src.is_file():
        raise C.GamekitError("VALIDATION_FAILED", f"source is not a file: {src}")
    check_license(license_id, author)
    size = src.stat().st_size
    if size <= 0:
        raise C.GamekitError("VALIDATION_FAILED", "source file is empty")
    if size > MAX_ASSET_BYTES:
        raise C.GamekitError("BAD_REQUEST", f"source is larger than {MAX_ASSET_BYTES} bytes")
    data = src.read_bytes()
    if len(data) != size:
        raise C.GamekitError("STALE", "source file changed while it was being read")
    checks = M.inspect_media(data, dest_path.suffix.lower())
    source_sha = C.sha256_bytes(data)
    request = {
        "kind": "asset.add",
        "dest": dest_res,
        "source_sha256": source_sha,
        "license": license_id,
        "author": author,
        "source_url": source_url,
        "ai_generated": ai_generated,
        "notes": notes,
        "replace": replace,
    }
    request_digest = C.digest(request)
    importable = dest_path.suffix.lower() in IMPORTABLE_EXTS
    journal = C.Journal(project)
    with C.project_lock(project, "asset.add", wait_seconds=30):
        prior = journal.replay_or_conflict(command_id, request_digest)
        if prior is not None:
            return prior
        src = _refuse_source(src)
        fresh = src.read_bytes()
        if C.sha256_bytes(fresh) != source_sha:
            raise C.GamekitError("STALE", "source file changed before the write")
        data = fresh
        C.refuse_if_editor_open(project, allow_open_editor)
        ledger_path = project.res_to_path(LEDGER_RES)
        ledger = _load_ledger(ledger_path)
        if dest_path.exists() and not dest_path.is_file():
            raise C.GamekitError("VALIDATION_FAILED", f"{dest_res} exists and is not a file")
        known = any(a.get("res") == dest_res for a in ledger["assets"])
        if not replace and (dest_path.exists() or known):
            raise C.GamekitError("CONFLICT", f"{dest_res} already exists; pass --replace to overwrite")
        entry = {
            "res": dest_res,
            "sha256": source_sha,
            "bytes": len(data),
            "license": license_id,
            "author": author,
            "source_url": source_url,
            "ai_generated": ai_generated,
            "notes": notes,
            "added_at": C.now_iso(),
            "checks": checks,
        }
        updated = _with_entry(ledger, entry)
        checkpoint_paths = [dest_path, ledger_path]
        if importable:
            checkpoint_paths.insert(1, Path(str(dest_path) + ".import"))
        C.checkpoint(project, command_id, checkpoint_paths)
        imported_full: dict[str, Any] | None = None
        try:
            C.atomic_write_bytes(dest_path, data)
            C.atomic_write_json(ledger_path, updated)
            imported_full = scene.refresh_import(project.root)
            problems = _readback_add(project, dest_path, dest_res, source_sha, len(data), importable)
            if problems:
                extra_errors = (imported_full or {}).get("errors") or []
                raise C.GamekitError(
                    "READBACK_MISMATCH",
                    "; ".join(problems[:8]),
                    problems=problems[:40],
                    godot_errors=extra_errors[:10],
                )
        except Exception:
            _restore_or_raise(project, command_id)
            raise
        receipt = {
            "ok": True,
            "status": "COMMITTED",
            "kind": "asset.add",
            "command_id": command_id,
            "project": project.project_id,
            "res": dest_res,
            "sha256": source_sha,
            "bytes": len(data),
            "license": license_id,
            "author": author,
            "source_url": source_url,
            "ai_generated": ai_generated,
            "notes": notes,
            "replaced": replace,
            "checks": checks,
            "readback": "LEDGER_SHA_IMPORT_MATCH",
            "import": _import_brief(imported_full),
            "at": entry["added_at"],
        }
        journal.append(command_id, request_digest, receipt)
        return receipt


def list_assets(project: C.Project) -> dict[str, Any]:
    with C.project_lock(project, "asset.list", wait_seconds=30):
        ledger = _load_ledger(project.res_to_path(LEDGER_RES))
    return {
        "ok": True,
        "kind": "asset.list",
        "project": project.project_id,
        "schema": LEDGER_SCHEMA,
        "count": len(ledger["assets"]),
        "assets": ledger["assets"],
    }


def verify(project: C.Project) -> dict[str, Any]:
    """Every ledger row exists with the recorded sha. Importable files under res://assets/ need a row."""
    with C.project_lock(project, "asset.verify", wait_seconds=30):
        ledger = _load_ledger(project.res_to_path(LEDGER_RES))
        problems: list[str] = []
        known: set[str] = set()
        for entry in ledger["assets"]:
            res = entry["res"]
            known.add(res)
            try:
                path = project.res_to_path(res)
            except C.GamekitError as exc:
                problems.append(f"{res}: {exc.detail}")
                continue
            if not path.is_file():
                problems.append(f"{res} missing")
                continue
            if C.sha256_file(path) != entry.get("sha256"):
                problems.append(f"{res} sha256 mismatch")
                continue
            if entry.get("bytes") != path.stat().st_size:
                problems.append(f"{res} byte size mismatch")
                continue
            try:
                check_license(str(entry.get("license") or ""), str(entry.get("author") or ""))
            except C.GamekitError as exc:
                problems.append(f"{res} license: {exc.detail}")
        untracked: list[str] = []
        assets_root = project.root / "assets"
        if assets_root.is_dir():
            for path in assets_root.rglob("*"):
                if not path.is_file() or path.is_symlink():
                    continue
                if path.suffix.lower() not in IMPORTABLE_EXTS:
                    continue
                try:
                    res = project.path_to_res(path)
                except C.GamekitError as exc:
                    problems.append(f"{path.name}: {exc.detail}")
                    continue
                if res not in known:
                    untracked.append(res)
    untracked.sort()
    return {
        "ok": not problems and not untracked,
        "kind": "asset.verify",
        "project": project.project_id,
        "checked": len(ledger["assets"]),
        "problems": problems,
        "untracked": untracked,
    }


def render_credits(assets: list[dict[str, Any]]) -> str:
    """Markdown grouped by license, with attribution text and an AI-generated section."""
    table = load_licenses()
    by_id = {rec["id"]: rec for rec in table["allowed"] + table.get("owner_review", [])
             if isinstance(rec, dict) and isinstance(rec.get("id"), str)}
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for asset in assets:
        lic = str(asset.get("license") or "unknown")
        if lic not in groups:
            groups[lic] = []
            order.append(lic)
        groups[lic].append(asset)
    lines = ["# Credits", ""]
    if not assets:
        lines.append("No assets are recorded in the ledger.")
        lines.append("")
    for lic in order:
        rec = by_id.get(lic, {})
        title = rec.get("name") or lic
        lines.append(f"## {title} (`{lic}`)")
        lines.append("")
        if rec.get("attribution_required") and rec.get("attribution"):
            lines.append(str(rec["attribution"]))
            lines.append("")
        for asset in groups[lic]:
            parts = [f"`{asset.get('res', '')}`", str(asset.get("author") or "unknown author")]
            if asset.get("source_url"):
                parts.append(str(asset["source_url"]))
            if asset.get("notes"):
                parts.append(str(asset["notes"]))
            lines.append("- " + " - ".join(parts))
        lines.append("")
    lines.append("## AI-generated content")
    lines.append("")
    ai = [a for a in assets if a.get("ai_generated")]
    if not ai:
        lines.append("No AI-generated assets are recorded in this ledger.")
    else:
        lines.append(
            "Store-page disclosure: this project includes AI-generated content. "
            "List these assets wherever the game is distributed."
        )
        lines.append("")
        for asset in ai:
            lines.append(
                f"- `{asset.get('res', '')}` - {asset.get('author') or 'unknown author'} - {asset.get('license')}"
            )
    lines.append("")
    return "\n".join(lines)


def _credits_out(project: C.Project, out: str) -> tuple[str, Path]:
    path = project.res_to_path(out)
    res = project.path_to_res(path)
    if res == LEDGER_RES:
        raise C.GamekitError("VALIDATION_FAILED", "credits output collides with the asset ledger")
    if path.suffix.lower() not in (".md", ".txt"):
        raise C.GamekitError("VALIDATION_FAILED", "credits output must be a .md or .txt res:// path")
    return res, path


def credits(
    project: C.Project,
    command_id: str,
    *,
    out: str = "res://CREDITS.md",
    allow_open_editor: bool = False,
) -> dict[str, Any]:
    """Write the credits markdown. Overwrites ``out``; the ledger is the hashed source."""
    command_id = C.validate_command_id(command_id)
    allow_open_editor = _require_bool(allow_open_editor, "allow_open_editor")
    out_res, out_path = _credits_out(project, out)
    ledger_path = project.res_to_path(LEDGER_RES)
    before = ledger_path.read_bytes() if ledger_path.is_file() else b""
    if before:
        _load_ledger(ledger_path)
    ledger_sha = C.sha256_bytes(before)
    request_digest = C.digest({"kind": "asset.credits", "out": out_res, "ledger_sha256": ledger_sha})
    journal = C.Journal(project)
    with C.project_lock(project, "asset.credits", wait_seconds=30):
        prior = journal.replay_or_conflict(command_id, request_digest)
        if prior is not None:
            return prior
        current = ledger_path.read_bytes() if ledger_path.is_file() else b""
        if C.sha256_bytes(current) != ledger_sha:
            raise C.GamekitError("STALE", "asset ledger changed before credits were written")
        ledger = _load_ledger(ledger_path)
        if any(a.get("res") == out_res for a in ledger["assets"]):
            raise C.GamekitError("CONFLICT", f"{out_res} is a ledgered asset; pick another --out path")
        C.refuse_if_editor_open(project, allow_open_editor)
        text = render_credits(ledger["assets"])
        data = text.encode("utf-8")
        C.checkpoint(project, command_id, [out_path])
        try:
            C.atomic_write_bytes(out_path, data)
            written = out_path.read_bytes()
            problems = []
            if written != data or C.sha256_bytes(written) != C.sha256_bytes(data):
                problems.append("credits file sha does not match the bytes that were written")
            got = written.decode("utf-8")
            if not got.startswith("# Credits") or "AI-generated content" not in got:
                problems.append("credits markdown is missing required sections")
            for asset in ledger["assets"]:
                res = str(asset.get("res") or "")
                author = str(asset.get("author") or "")
                if res and res not in got:
                    problems.append(f"credits missing {res}")
                if author and author not in got:
                    problems.append(f"credits missing author {author}")
            if problems:
                raise C.GamekitError("READBACK_MISMATCH", "; ".join(problems[:8]), problems=problems[:40])
        except Exception:
            _restore_or_raise(project, command_id)
            raise
        receipt = {
            "ok": True,
            "status": "COMMITTED",
            "kind": "asset.credits",
            "command_id": command_id,
            "project": project.project_id,
            "res": out_res,
            "sha256": C.sha256_bytes(data),
            "bytes": len(data),
            "assets": len(ledger["assets"]),
            "readback": "FILE_SHA_MATCH",
            "at": C.now_iso(),
        }
        journal.append(command_id, request_digest, receipt)
        return receipt


def _cmd_add(a: argparse.Namespace) -> dict[str, Any]:
    return add(
        C.get_project(a.project),
        a.source,
        a.dest,
        a.license,
        a.author,
        source_url=a.source_url,
        ai_generated=bool(a.ai_generated),
        notes=a.notes,
        command_id=a.command_id,
        replace=bool(a.replace),
        allow_open_editor=bool(a.allow_open_editor),
    )


def _cmd_list(a: argparse.Namespace) -> dict[str, Any]:
    return list_assets(C.get_project(a.project))


def _cmd_verify(a: argparse.Namespace) -> dict[str, Any]:
    return verify(C.get_project(a.project))


def _cmd_credits(a: argparse.Namespace) -> dict[str, Any]:
    return credits(
        C.get_project(a.project),
        a.command_id,
        out=a.out,
        allow_open_editor=bool(a.allow_open_editor),
    )


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("asset", help="copy licensed assets into a project, list them, verify hashes, write credits")
    ps = p.add_subparsers(dest="action", required=True)

    add_p = ps.add_parser("add", help="copy a source file to res:// and record license, author, and media checks")
    add_p.add_argument("project")
    add_p.add_argument("source", help="host path of the file to copy")
    add_p.add_argument("--dest", required=True, help="res:// path inside the project, usually res://assets/...")
    add_p.add_argument("--license", required=True, help="SPDX-style id from licenses.json, or self-made")
    add_p.add_argument("--author", required=True)
    add_p.add_argument("--source-url", default="")
    add_p.add_argument("--ai-generated", action="store_true", help="flag the asset for the store-page AI disclosure")
    add_p.add_argument("--notes", default="")
    add_p.add_argument("--command-id", required=True)
    add_p.add_argument("--replace", action="store_true", help="overwrite an existing dest and its ledger row")
    add_p.add_argument("--allow-open-editor", action="store_true")
    add_p.set_defaults(func=_cmd_add)

    list_p = ps.add_parser("list", help="print the asset ledger")
    list_p.add_argument("project")
    list_p.set_defaults(func=_cmd_list)

    verify_p = ps.add_parser("verify", help="check ledger hashes and report untracked importable files under res://assets/")
    verify_p.add_argument("project")
    verify_p.set_defaults(func=_cmd_verify)

    credits_p = ps.add_parser("credits", help="write CREDITS.md grouped by license, including AI-generated content")
    credits_p.add_argument("project")
    credits_p.add_argument("--out", default="res://CREDITS.md")
    credits_p.add_argument("--command-id", required=True)
    credits_p.add_argument("--allow-open-editor", action="store_true")
    credits_p.set_defaults(func=_cmd_credits)
