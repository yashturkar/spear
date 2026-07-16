import json
import subprocess
from pathlib import Path


REPO = Path("/home/yashturkar/Workspace/spear")
RUN_DIR = REPO / ".control-tower/runs/infinigen_indoors_kitchen_20260710T235251Z"
UNREAL_PAK = Path("/home/yashturkar/Linux_Unreal_Engine_5.5.4/Engine/Binaries/Linux/UnrealPak")
WORLD = "infinigen_indoors_kitchen"
PAKS = {
    "archive": REPO / "cpp/unreal_projects/SpearSim/Standalone-Development/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak",
    "staged": REPO / "cpp/unreal_projects/SpearSim/Saved/StagedBuilds/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak",
}


def pak_entry(ext):
    return f"SpearSim/Content/SPEAR/Scenes/{WORLD}/Maps/{WORLD}.{ext}"


def list_pak(label, pak):
    log_path = RUN_DIR / f"{label}_pak_list.log"
    if not pak.exists():
        log_path.write_text(f"missing pak: {pak}\n", encoding="utf-8")
        return 127, []
    with log_path.open("w", encoding="utf-8") as out:
        rc = subprocess.run([str(UNREAL_PAK), str(pak), "-List"], stdout=out, stderr=subprocess.STDOUT).returncode
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return rc, lines


def main():
    summary = {
        "world": WORLD,
        "required_entries": {"umap": pak_entry("umap"), "uexp": pak_entry("uexp")},
        "paks": {},
    }
    ok = True
    for label, pak in PAKS.items():
        rc, entries = list_pak(label, pak)
        has_umap = any(pak_entry("umap") in entry for entry in entries)
        has_uexp = any(pak_entry("uexp") in entry for entry in entries)
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
    summary["ok"] = ok
    (RUN_DIR / "pak_verification_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (RUN_DIR / "pak_verification_summary.txt").open("w", encoding="utf-8") as out:
        out.write(f"ok={ok}\n")
        out.write(f"required_umap={pak_entry('umap')}\n")
        out.write(f"required_uexp={pak_entry('uexp')}\n")
        for label, result in summary["paks"].items():
            out.write(
                f"{label}_pak={result['path']} exists={result['exists']} "
                f"size_bytes={result['size_bytes']} list_exit={result['unrealpak_list_exit']} "
                f"has_umap={result['has_umap']} has_uexp={result['has_uexp']} ok={result['ok']}\n"
            )
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
