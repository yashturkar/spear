#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from pathlib import Path


REPO = Path("/home/yashturkar/Workspace/spear")
RUN_DIR = REPO / ".control-tower/runs/cook_infinigen_kitchen_live_20260711T010155Z"
UNREAL_PAK = Path("/home/yashturkar/Linux_Unreal_Engine_5.5.4/Engine/Binaries/Linux/UnrealPak")
MAP_PATH = "/Game/SPEAR/Scenes/infinigen_indoors_kitchen/Maps/infinigen_indoors_kitchen"
REQUIRED = [
    "SpearSim/Content/SPEAR/Scenes/infinigen_indoors_kitchen/Maps/infinigen_indoors_kitchen.umap",
    "SpearSim/Content/SPEAR/Scenes/infinigen_indoors_kitchen/Maps/infinigen_indoors_kitchen.uexp",
]
PAKS = {
    "archive": REPO / "cpp/unreal_projects/SpearSim/Standalone-Development/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak",
    "staged": REPO / "cpp/unreal_projects/SpearSim/Saved/StagedBuilds/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak",
}


def list_pak(label: str, pak: Path) -> tuple[int, set[str]]:
    log_path = RUN_DIR / f"{label}_pak_list.log"
    if not pak.exists():
        log_path.write_text(f"missing pak: {pak}\n")
        return 100, set()
    with log_path.open("w") as out:
        rc = subprocess.run([str(UNREAL_PAK), str(pak), "-List"], stdout=out, stderr=subprocess.STDOUT).returncode
    text = log_path.read_text(errors="replace")
    entries = set(re.findall(r'"([^"]+)"', text))
    return rc, entries


def stat_desc(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    return {
        "exists": True,
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "mtime_epoch": path.stat().st_mtime,
    }


def main() -> int:
    paks = {}
    all_ok = True
    for label, pak in PAKS.items():
        rc, entries = list_pak(label, pak)
        required_present = {entry: entry in entries for entry in REQUIRED}
        ok = rc == 0 and all(required_present.values())
        all_ok = all_ok and ok
        paks[label] = {
            **stat_desc(pak),
            "unrealpak_list_exit": rc,
            "required_entries_present": required_present,
            "ok": ok,
        }

    source_umap = REPO / "cpp/unreal_projects/SpearSim/Content/SPEAR/Scenes/infinigen_indoors_kitchen/Maps/infinigen_indoors_kitchen.umap"
    summary = {
        "status": "success" if all_ok else "failed",
        "map_path": MAP_PATH,
        "source_umap": stat_desc(source_umap),
        "required_entries": REQUIRED,
        "paks": paks,
    }
    (RUN_DIR / "pak_verification_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    with (RUN_DIR / "pak_verification_summary.txt").open("w") as out:
        out.write(f"status={summary['status']}\n")
        out.write(f"map_path={MAP_PATH}\n")
        out.write(f"source_umap={source_umap} exists={source_umap.exists()}\n")
        for label, desc in paks.items():
            out.write(
                f"{label}_pak={desc['path']} exists={desc['exists']} "
                f"size_bytes={desc.get('size_bytes')} mtime_epoch={desc.get('mtime_epoch')} "
                f"unrealpak_list_exit={desc['unrealpak_list_exit']} ok={desc['ok']}\n"
            )
            for entry, present in desc["required_entries_present"].items():
                out.write(f"{label}_entry {entry} present={present}\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if all_ok else 10


if __name__ == "__main__":
    sys.exit(main())
