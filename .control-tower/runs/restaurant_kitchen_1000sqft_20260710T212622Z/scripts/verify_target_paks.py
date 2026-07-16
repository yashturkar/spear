#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from pathlib import Path


REPO = Path("/home/yashturkar/Workspace/spear")
RUN_DIR = REPO / ".control-tower/runs/restaurant_kitchen_1000sqft_20260710T212622Z"
UNREAL_PAK = Path("/home/yashturkar/Linux_Unreal_Engine_5.5.4/Engine/Binaries/Linux/UnrealPak")
TARGET_MAP = "/Game/SPEAR/Scenes/restaurant_kitchen_1000sqft/Maps/restaurant_kitchen_1000sqft"
PAKS = {
    "archive": REPO / "cpp/unreal_projects/SpearSim/Standalone-Development/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak",
    "staged": REPO / "cpp/unreal_projects/SpearSim/Saved/StagedBuilds/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak",
}


def pak_entry(ext):
    return f"SpearSim/Content/{TARGET_MAP[len('/Game/'):]}.{ext}"


def list_pak(label, pak):
    log_path = RUN_DIR / f"{label}_pak_list.log"
    if not pak.exists():
        log_path.write_text(f"missing pak: {pak}\n")
        return 100, set()
    with log_path.open("w") as out:
        rc = subprocess.run([str(UNREAL_PAK), str(pak), "-List"], stdout=out, stderr=subprocess.STDOUT).returncode
    entries = set(re.findall(r'"([^"]+)"', log_path.read_text(errors="replace")))
    return rc, entries


def main():
    summary = {
        "target_map": TARGET_MAP,
        "required_entries": {"umap": pak_entry("umap"), "uexp": pak_entry("uexp")},
        "paks": {},
    }
    ok = True
    for label, pak in PAKS.items():
        rc, entries = list_pak(label, pak)
        has_umap = pak_entry("umap") in entries
        has_uexp = pak_entry("uexp") in entries
        pak_ok = rc == 0 and has_umap and has_uexp
        ok = ok and pak_ok
        summary["paks"][label] = {
            "path": str(pak),
            "exists": pak.exists(),
            "size_bytes": pak.stat().st_size if pak.exists() else None,
            "unrealpak_list_exit": rc,
            "has_umap": has_umap,
            "has_uexp": has_uexp,
            "ok": pak_ok,
        }
    summary["status"] = "success" if ok else "failed"
    summary_path = RUN_DIR / "pak_verification_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    text_path = RUN_DIR / "pak_verification_summary.txt"
    with text_path.open("w") as out:
        out.write(f"status={summary['status']}\n")
        out.write(f"target_map={TARGET_MAP}\n")
        out.write(f"required_umap={pak_entry('umap')}\n")
        out.write(f"required_uexp={pak_entry('uexp')}\n")
        for label, result in summary["paks"].items():
            out.write(
                f"{label}_pak={result['path']} exists={result['exists']} "
                f"size_bytes={result['size_bytes']} list_exit={result['unrealpak_list_exit']} "
                f"has_umap={str(result['has_umap']).lower()} "
                f"has_uexp={str(result['has_uexp']).lower()} ok={str(result['ok']).lower()}\n"
            )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if ok else 10


if __name__ == "__main__":
    sys.exit(main())
