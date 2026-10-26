import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
data = json.loads((root / "data" / "sf_sheet_cells.json").read_text(encoding="utf-8"))
flat = []
for x, y, w, h in data["cells"]:
    flat.extend([x, y, w, h])
lines = [
    "class_name SfSheetData",
    "extends RefCounted",
    "static var CELLS: PackedInt32Array = PackedInt32Array([%s])" % ",".join(str(n) for n in flat),
]
for name, frames in data["clips"].items():
    lines.append(
        "static var %s: PackedInt32Array = PackedInt32Array([%s])" % (name.upper(), ",".join(str(n) for n in frames))
    )
text = "\n".join(lines) + "\n"
(root / "game" / "presentation" / "sf_sheet_data.gd").write_text(text, encoding="utf-8")
print("cells", len(data["cells"]))
