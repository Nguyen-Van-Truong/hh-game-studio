"""Original GT01 cube, trusted factory-startup background process only."""
from pathlib import Path
import argparse
import json
import math
import os
import sys
import tempfile
import bpy


def safe_output(raw):
    path = Path(raw).absolute()
    if ".." in Path(raw).parts or path.suffix != ".blend":
        raise ValueError("require new .blend output without traversal")
    for part in [path, *path.parents]:
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("linked output path")
    if path.exists() or not path.parent.is_dir():
        raise ValueError("output exists or parent missing")
    return path


def verify():
    if bpy.app.version[:3] != (5, 2, 1):
        raise RuntimeError("Blender pin mismatch")
    if len(bpy.data.objects) != 1 or len(bpy.data.meshes) != 1:
        raise RuntimeError("expected one original mesh")
    cube = bpy.data.objects["GT01_Cube"]
    if cube.type != "MESH" or len(cube.data.vertices) != 8 or len(cube.data.polygons) != 6:
        raise RuntimeError("cube topology mismatch")
    for row in range(4):
        for col in range(4):
            if not math.isclose(cube.matrix_world[row][col], float(row == col), abs_tol=1e-6):
                raise RuntimeError("nonidentity transform")
    for axis in range(3):
        values = [v.co[axis] for v in cube.data.vertices]
        if not math.isclose(min(values), -0.5, abs_tol=1e-6) or not math.isclose(max(values), 0.5, abs_tol=1e-6):
            raise RuntimeError("bounds mismatch")
    material = cube.active_material
    if material is None or material.name != "GT01_Material":
        raise RuntimeError("material mismatch")
    expected = (0.12, 0.55, 0.8, 1.0)
    if any(not math.isclose(a, b, abs_tol=1e-6) for a, b in zip(material.diffuse_color, expected)):
        raise RuntimeError("material color mismatch")
    units = bpy.context.scene.unit_settings
    if units.system != "METRIC" or units.scale_length != 1.0 or bpy.data.libraries or bpy.data.brushes:
        raise RuntimeError("units or external dependency mismatch")
    return {"vertices": len(cube.data.vertices), "polygons": len(cube.data.polygons)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    target = safe_output(args.output)
    if not bpy.app.background or bpy.app.version[:3] != (5, 2, 1):
        raise RuntimeError("requires background Blender5.2.1")
    # Invoked only with --factory-startup in an owned process.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # Factory brush assets are unnecessary for this source fixture; removing
    # their datablocks prevents save warnings and installed asset path leakage.
    for brush in list(bpy.data.brushes):
        bpy.data.brushes.remove(brush)
    for material in list(bpy.data.materials):
        bpy.data.materials.remove(material)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    cube = bpy.context.object
    cube.name = "GT01_Cube"
    material = bpy.data.materials.new("GT01_Material")
    material.diffuse_color = (0.12, 0.55, 0.8, 1.0)
    cube.data.materials.append(material)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    verify()
    staging_dir = Path(tempfile.mkdtemp(prefix=".gt01-", dir=target.parent))
    staged = staging_dir / "fixture.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(staged), check_existing=False)
    bpy.ops.wm.open_mainfile(filepath=str(staged), load_ui=False, use_scripts=False)
    mesh = verify()
    safe_output(str(target))
    # Hard link publication is exclusive on Windows and POSIX. A concurrent
    # output cannot be replaced; unsupported filesystems fail explicitly.
    os.link(staged, target)
    staged.unlink()
    staging_dir.rmdir()
    print("GT01_BLENDER_TRACE " + json.dumps({"result": "PASS", "filename": target.name,
          "version": bpy.app.version_string, "axis": "Z_UP_RIGHT_HANDED",
          "origin": [0, 0, 0], "unit_meters": 1, **mesh}))


if __name__ == "__main__":
    main()
