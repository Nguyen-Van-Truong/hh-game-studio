"""Engine-free verification of the sealed S229 terminal failure."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "studio/.local/reviews/gt06-s229-formal-01"
MANIFEST = RAW / "raw-manifest.json"
ARCHIVE = ROOT / "studio/.local/archives/gt06-s229-formal-01-s230-terminal.zip"
MANIFEST_SHA = "30f0bba3ba413754d8055db62ecf1de36e1c6b43b547a99a8bb31ab393df949f"
ARCHIVE_SHA = "391f0e6347f1fd1112366144b00622ac5d895ba669ad81a718e6918a4e29c92b"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    assert sha(MANIFEST) == MANIFEST_SHA
    manifest = json.loads(MANIFEST.read_bytes())
    assert manifest["authority"] == 0 and manifest["formal_acceptance"] is False
    rows = {row["path"]: row for row in manifest["files"]}
    assert len(rows) == 339
    for name, row in rows.items():
        source = RAW / name[4:] if name.startswith("raw/") else RAW.parent / ("gt06-s229-formal-01-supervisor/" + name[11:])
        assert source.is_file()
        assert source.stat().st_size == row["bytes"]
        assert sha(source) == row["sha256"]
    assert sha(ARCHIVE) == ARCHIVE_SHA

    analysis = json.loads((Path(__file__).parent / "analysis.json").read_bytes())
    assert analysis["authority"] == 0 and analysis["formal_acceptance"] is False
    assert analysis["screen_failure"] == "CAMPAIGN_RETAINED_COUNTER_GROWTH"
    assert analysis["baseline_objects"] == 71128 and analysis["editor_objects_batch16"] == 71130
    assert analysis["host_owner_actual_exit"] == 1 and analysis["import_actual_exit"] == 0
    assert analysis["measurement_defect_proven"] is False
    assert analysis["leak_owner_rootcause_proven"] is False

    seal = json.loads((Path(__file__).parent / "terminal-seal.json").read_bytes())
    assert seal["raw_manifest_sha256"] == MANIFEST_SHA
    assert seal["archive_sha256"] == ARCHIVE_SHA
    assert seal["verified_files"] == 340
    assert seal["editor_target_exit"] is None
    assert seal["jobs_zero_closed"] is True and seal["handles_released"] is True

    with zipfile.ZipFile(ARCHIVE) as archive:
        names = set(archive.namelist())
        assert "raw-manifest.json" in names
        assert all(name in names for name in rows)
        assert len(names) == 340
    print(json.dumps({"authority": 0, "formal_acceptance": False,
                      "verified_raw_entries": len(rows), "archive_members": 340,
                      "failure": analysis["screen_failure"]}, sort_keys=True))


if __name__ == "__main__":
    main()
