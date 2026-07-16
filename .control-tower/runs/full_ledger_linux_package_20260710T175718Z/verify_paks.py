#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from pathlib import Path


REPO = Path("/home/yashturkar/Workspace/spear")
RUN_DIR = REPO / ".control-tower/runs/full_ledger_linux_package_20260710T175718Z"
LEDGER = REPO / "docs/environment_ledger.json"
UNREAL_PAK = Path("/home/yashturkar/Linux_Unreal_Engine_5.5.4/Engine/Binaries/Linux/UnrealPak")
PAKS = {
    "archive": REPO / "cpp/unreal_projects/SpearSim/Standalone-Development/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak",
    "staged": REPO / "cpp/unreal_projects/SpearSim/Saved/StagedBuilds/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak",
}


def pak_entry_for(unreal_map_path: str, ext: str) -> str:
    if not unreal_map_path.startswith("/Game/"):
        raise ValueError(f"unsupported map path: {unreal_map_path}")
    return f"SpearSim/Content/{unreal_map_path[len('/Game/'):]}.{ext}"


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


def main() -> int:
    ledger = json.loads(LEDGER.read_text())
    targets = [env for env in ledger["environments"] if env.get("unreal_map_path") is not None]

    pak_results = {}
    for label, pak in PAKS.items():
        rc, entries = list_pak(label, pak)
        pak_results[label] = {
            "path": str(pak),
            "exists": pak.exists(),
            "size_bytes": pak.stat().st_size if pak.exists() else None,
            "mtime": pak.stat().st_mtime if pak.exists() else None,
            "unrealpak_list_exit": rc,
            "entries": entries,
        }

    rows = []
    all_ok = True
    for env in targets:
        map_path = env["unreal_map_path"]
        source_path = REPO / env["local_umap_path"]
        row = {
            "alias": env["alias"],
            "unreal_map_path": map_path,
            "source_umap_exists": source_path.exists(),
            "archive_umap": pak_entry_for(map_path, "umap") in pak_results["archive"]["entries"],
            "archive_uexp": pak_entry_for(map_path, "uexp") in pak_results["archive"]["entries"],
            "staged_umap": pak_entry_for(map_path, "umap") in pak_results["staged"]["entries"],
            "staged_uexp": pak_entry_for(map_path, "uexp") in pak_results["staged"]["entries"],
        }
        row["archive_ok"] = row["archive_umap"] and row["archive_uexp"]
        row["staged_ok"] = row["staged_umap"] and row["staged_uexp"]
        row["ok"] = row["archive_ok"] and row["staged_ok"]
        rows.append(row)
        all_ok = all_ok and row["ok"]

    for label, result in pak_results.items():
        all_ok = all_ok and result["unrealpak_list_exit"] == 0

    coverage_md = RUN_DIR / "coverage_table.md"
    with coverage_md.open("w") as out:
        out.write("| alias | unreal_map_path | archive .umap | archive .uexp | staged .umap | staged .uexp |\n")
        out.write("| --- | --- | --- | --- | --- | --- |\n")
        for row in rows:
            out.write(
                f"| {row['alias']} | {row['unreal_map_path']} | "
                f"{'yes' if row['archive_umap'] else 'no'} | "
                f"{'yes' if row['archive_uexp'] else 'no'} | "
                f"{'yes' if row['staged_umap'] else 'no'} | "
                f"{'yes' if row['staged_uexp'] else 'no'} |\n"
            )

    summary = {
        "status": "success" if all_ok else "failed",
        "ledger_target_count": len(targets),
        "all_required_entries_present": all_ok,
        "paks": {
            label: {k: v for k, v in result.items() if k != "entries"}
            for label, result in pak_results.items()
        },
        "coverage": rows,
    }
    (RUN_DIR / "verification_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    with (RUN_DIR / "verification_summary.txt").open("w") as out:
        out.write(f"status={summary['status']}\n")
        out.write(f"ledger_target_count={len(targets)}\n")
        out.write(f"all_required_entries_present={str(all_ok).lower()}\n")
        for label, result in summary["paks"].items():
            out.write(
                f"{label}_pak={result['path']} exists={result['exists']} "
                f"size_bytes={result['size_bytes']} unrealpak_list_exit={result['unrealpak_list_exit']}\n"
            )
        out.write(f"coverage_table={coverage_md}\n")
        out.write("\n")
        out.write(coverage_md.read_text())

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if all_ok else 10


if __name__ == "__main__":
    sys.exit(main())
