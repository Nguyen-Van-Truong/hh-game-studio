"""Engine-free verification of the sealed S228 provider differential."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "studio/.local/reviews/gt06-s228-phase-rss-01"
ARCHIVE = ROOT / "studio/.local/archives/gt06-s228-phase-rss-01-s228.zip"
MANIFEST_SHA = "1410e8116c2279a1c9f991233bbe5cf4e2ee058f7ab3d68742692ebfa63b4ec1"
ARCHIVE_SHA = "75941c6e4ecf94b0094b6eb7da9807a15f917baa0541e2bcf7ef86ef0b78bdd5"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = RAW / "raw-manifest.json"
    assert digest(manifest_path) == MANIFEST_SHA
    manifest = json.loads(manifest_path.read_bytes())
    assert manifest["authority"] == 0
    assert manifest["formal_acceptance"] is False
    assert manifest["run_id"] == "gt06-s228-phase-rss-01"
    rows = {row["path"]: row for row in manifest["files"]}
    assert len(rows) == 8
    for rel, row in rows.items():
        path = RAW / rel
        assert path.is_file()
        assert path.stat().st_size == row["bytes"]
        assert digest(path) == row["sha256"]
    assert digest(ARCHIVE) == ARCHIVE_SHA

    analysis = json.loads((RAW / "analysis.json").read_bytes())
    assert analysis["authority"] == 0
    assert analysis["formal_acceptance"] is False
    assert analysis["external_sample_count"] == 440
    assert analysis["internal_sample_count"] == 373
    assert analysis["comparable_pairs"] == 373
    assert analysis["provider_agreement_not_rootcause"] is True
    assert analysis["measurement_defect_proven"] is False
    assert analysis["leak_owner_rootcause_proven"] is False
    assert analysis["native_actual_exit"]["exit_code"] == 0

    process_exit = json.loads((RAW / "native-process-exit.json").read_bytes())
    assert process_exit["actual_exit"] == 0
    assert process_exit["stderr_bytes"] == 0

    refs = json.loads((RAW / "internal-references.json").read_bytes())
    assert refs["authority"] == 0 and refs["formal_acceptance"] is False
    native_raw = ROOT / "studio/.local/reviews"
    for row in refs["files"]:
        path = native_raw / row["raw_path"]
        assert path.is_file()
        assert path.stat().st_size == row["bytes"]
        assert digest(path) == row["sha256"]
    with zipfile.ZipFile(ARCHIVE) as archive:
        names = set(archive.namelist())
        assert all(("raw/" + row["path"]) in names for row in rows.values())
    print(json.dumps({"authority": 0, "formal_acceptance": False,
                      "verified_files": len(rows), "comparable_pairs": 373,
                      "archive_sha256": ARCHIVE_SHA}, sort_keys=True))


if __name__ == "__main__":
    main()
