import json
import os
import sys
from pathlib import Path

import bpy


def mesh_stats(obj):
    mesh = obj.data
    return {
        "name": obj.name,
        "vertices": len(mesh.vertices),
        "polygons": len(mesh.polygons),
        "materials": len(obj.material_slots),
    }


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: blender --background scene.blend --python blender_source_stats.py -- output.json")
    marker = sys.argv.index("--") if "--" in sys.argv else len(sys.argv) - 1
    output_path = Path(sys.argv[marker + 1])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    mesh_details = sorted((mesh_stats(obj) for obj in meshes), key=lambda item: item["vertices"], reverse=True)
    blend_path = Path(bpy.data.filepath)
    report = {
        "blend_file": str(blend_path),
        "file_size_bytes": blend_path.stat().st_size if blend_path.exists() else None,
        "object_count": len(bpy.data.objects),
        "mesh_object_count": len(meshes),
        "vertices": sum(item["vertices"] for item in mesh_details),
        "polygons": sum(item["polygons"] for item in mesh_details),
        "material_count": len(bpy.data.materials),
        "image_count": len(bpy.data.images),
        "light_count": sum(1 for obj in bpy.data.objects if obj.type == "LIGHT"),
        "camera_count": sum(1 for obj in bpy.data.objects if obj.type == "CAMERA"),
        "representative_objects": [item["name"] for item in mesh_details[:30]],
        "largest_meshes": mesh_details[:20],
    }
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
