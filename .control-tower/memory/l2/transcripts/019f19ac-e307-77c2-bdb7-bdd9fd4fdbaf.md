## User

# Scout

You are Scout, the research and discovery specialist.

## Responsibilities

- Investigate technical options and tradeoffs.
- Validate approaches before implementation.
- Produce actionable recommendations and risk notes.
- Stay concrete and decision-oriented.

## Restrictions

- Default to read-heavy work unless the packet explicitly requests a written artifact.
- Do not present weak speculation as fact.
- Return a ResultPacket only.

## Policy

```yaml
agent: Scout
role: research
allowed_paths:
  - docs/
  - .control-tower/
  - src/
prohibited_actions:
  - broad source edits
  - undocumented assumptions
```

## Task Packet

```json
{
  "schema_version": "1.0.0",
  "packet_type": "task",
  "packet_id": "a23f9fe6-d876-4641-bd71-192cb9bc4418",
  "trace_id": "0d6ee34e-f1be-4d44-9985-ac10f6280837",
  "parent_packet_id": null,
  "created_at": "2026-06-30T17:56:20Z",
  "from_agent": "tower",
  "to_agent": "scout",
  "task_type": "research",
  "priority": "high",
  "project_id": "spear",
  "session_id": "tower-session",
  "title": "Explain SPEAR world packaging and archive paths",
  "objective": "Investigate whether SPEAR imported worlds are self-contained and identify exactly what paths should be archived or shared for source-level Unreal content, cooked runnable builds, and Infinigen regeneration sources.",
  "instructions": [
    "Inspect the local Unreal project content layout for imported scenes under cpp/unreal_projects/SpearSim/Content/SPEAR/Scenes and identify map/asset directory structure.",
    "Inspect packaged/staged output locations for standalone runnable builds and clarify whether a single world can be archived separately from a cooked package.",
    "Inspect the Infinigen output folders for college_classroom and one_bed_apartment to distinguish source .blend/FBX/log artifacts from SPEAR runtime assets.",
    "Answer in operational terms: what to archive to share with another SPEAR developer, what to archive to share a runnable sim, and what to archive to regenerate/reimport later.",
    "Do not edit files, do not run long jobs, do not perform Git operations."
  ],
  "constraints": [],
  "inputs": {
    "files": [],
    "artifacts": [],
    "references": []
  },
  "expected_outputs": [
    "Concise explanation of self-contained versus dependent assets.",
    "Exact local paths and recommended archive groupings.",
    "Caveats about cooked PAKs, project dependencies, and disabled material/texture/collision imports."
  ],
  "definition_of_done": [
    "Scout returns a ResultPacket with actionable archive/share guidance."
  ],
  "memory_context_refs": [
    ".control-tower/docs/state/current-status.md"
  ],
  "doc_context_refs": [
    "docs/importing_and_exporting_assets.md",
    "docs/running_our_example_applications.md"
  ],
  "time_budget": {
    "soft_seconds": 180,
    "hard_seconds": 600
  },
  "requires_review": true,
  "allow_partial": false,
  "metadata": {}
}
```

## Output Contract

Return only a JSON object that conforms to `.control-tower/schemas/packets/result.schema.json`.
Do not wrap the JSON in markdown.
If blocked, return a valid ResultPacket with `status` set to `blocked` and explain why in `summary` and `findings`.

## Agent

{"schema_version":"1.0.0","packet_type":"result","packet_id":"a23f9fe6-d876-4641-bd71-192cb9bc4418-result","trace_id":"0d6ee34e-f1be-4d44-9985-ac10f6280837","parent_packet_id":"a23f9fe6-d876-4641-bd71-192cb9bc4418","created_at":"2026-06-30T18:05:00Z","from_agent":"scout","to_agent":"tower","status":"success","summary":"Imported SPEAR worlds are self-contained at the Unreal source-content directory level only when the whole per-world Content/SPEAR/Scenes/<world> folder is kept together. A .umap alone is not self-contained because it references mesh assets under the sibling Meshes directory. Cooked runnable output is currently a monolithic Standalone-Development Linux archive with one SpearSim-Linux.pak, so a single cooked world is not cleanly separable unless a dedicated per-world/DLC PAK workflow is added. Infinigen output folders are regeneration/reimport sources, not SPEAR runtime assets.","work_completed":["Read durable context in .control-tower/docs/state/current-status.md, docs/importing_and_exporting_assets.md, and docs/running_our_example_applications.md.","Inspected local Unreal source-content layout under cpp/unreal_projects/SpearSim/Content/SPEAR/Scenes.","Verified imported scene structure: one_bed_apartment has Maps/one_bed_apartment.umap plus Meshes with 112 total files and 689M; college_classroom has Maps/college_classroom.umap plus Meshes with 286 total files and 17M; infinigen_indoors_0000 also follows Maps plus Meshes structure with 591 files.","Inspected packaged output: cpp/unreal_projects/SpearSim/Standalone-Development is 4.9G; shareable Linux archive root is cpp/unreal_projects/SpearSim/Standalone-Development/Linux; the package contains cpp/unreal_projects/SpearSim/Standalone-Development/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak at 3427693130 bytes. The staged equivalent is cpp/unreal_projects/SpearSim/Saved/StagedBuilds/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak.","Inspected Infinigen source/export folders for one_bed_apartment_spear_light and college_classroom and separated coarse .blend/regeneration artifacts from exported FBX/log artifacts."],"artifacts_changed":[],"artifacts_created":[],"artifacts_deleted":[],"findings":[{"severity":"info","message":"For source-level sharing with another SPEAR developer, archive the whole Unreal content folder for each world, preserving its relative path: cpp/unreal_projects/SpearSim/Content/SPEAR/Scenes/one_bed_apartment, cpp/unreal_projects/SpearSim/Content/SPEAR/Scenes/college_classroom, or cpp/unreal_projects/SpearSim/Content/SPEAR/Scenes/infinigen_indoors_0000. Do not share only Maps/*.umap; the maps depend on sibling Meshes/*.uasset files."},{"severity":"info","message":"Recommended source-content archive grouping: one archive per world folder under Content/SPEAR/Scenes, restored to the same relative path in a compatible SpearSim Unreal project and UE/SPEAR version. Current imported worlds do not have Materials or Textures subdirectories because material and texture import was disabled."},{"severity":"info","message":"For a runnable simulator, archive cpp/unreal_projects/SpearSim/Standalone-Development/Linux as the shareable build output. That directory includes SpearSim.sh, binaries, Engine runtime dependencies, and SpearSim/Content/Paks/SpearSim-Linux.pak. The Saved/StagedBuilds/Linux/SpearSim tree is a staging copy/intermediate, not the preferred handoff path."},{"severity":"warning","message":"A single cooked world cannot currently be archived as a clean standalone runnable artifact from the observed output. The current cook/package flow produced one monolithic SpearSim-Linux.pak containing the cooked project payload. The Saved/Cooked per-world .uasset/.uexp/.ubulk files are not enough by themselves for a runnable sim and should not be treated as a portable single-world package."},{"severity":"info","message":"For one_bed_apartment regeneration/reimport, archive /home/yashturkar/Workspace/infinigen/outputs/one_bed_apartment_spear_light plus provenance from /home/yashturkar/Workspace/infinigen/outputs/one_bed_apartment/one_bed_floorplan.json and optionally run_generate_one_bed.sh. Key artifacts include coarse/scene.blend, coarse/polycounts.txt, spear_export_r256/export_scene.blend/export_scene.fbx, spear_export_r256/export_logs.log, and logs/*.log."},{"severity":"info","message":"For college_classroom regeneration/reimport, archive /home/yashturkar/Workspace/infinigen/outputs/college_classroom. Key artifacts include coarse/scene.blend, scripts/create_college_classroom.py, spear_export_r256/export_scene.blend/export_scene.fbx, spear_export_r256/export_logs.log, logs/*.log, preview, and status_college_classroom_20260630T145523Z.txt."},{"severity":"warning","message":"Infinigen folders are not SPEAR runtime assets. SPEAR loads the imported Unreal .umap/.uasset content or cooked PAK output; Infinigen .blend, FBX, scripts, floorplans, and logs are for re-exporting/reimporting or auditing provenance."},{"severity":"warning","message":"Both one_bed_apartment and college_classroom were imported with --no-auto-generate-collision --no-import-materials --no-import-textures. Expect limited/default visual material fidelity and likely missing generated collision unless later repaired; inspect visual quality, scale, lighting, collision/navigation behavior, and PlayerStart usability before data collection."}],"follow_up_recommendations":["Add a short docs section that formalizes three archive bundles: Unreal source content, full standalone runnable build, and Infinigen regeneration bundle.","If single-world cooked sharing is required, define and validate a dedicated per-world PAK or DLC-style packaging workflow instead of relying on the current monolithic SpearSim-Linux.pak.","Before archiving for external use, run a small restore test in a clean compatible SPEAR checkout: copy the per-world Content/SPEAR/Scenes folder, open/cook the map, and launch with --map-path."],"review_requested":true,"doc_update_needed":true,"memory_worthy":["Imported Infinigen SPEAR worlds are source-level self-contained only as full Content/SPEAR/Scenes/<world> folders containing Maps and Meshes; .umap files alone are not enough.","Current runnable Linux package is cpp/unreal_projects/SpearSim/Standalone-Development/Linux with a monolithic SpearSim-Linux.pak; single cooked worlds are not cleanly separable under the current packaging flow.","Regeneration/reimport sources live under /home/yashturkar/Workspace/infinigen/outputs/<scene>; they are not runtime SPEAR assets."],"metrics":{"tokens_used":0,"files_touched":0,"tests_added":0,"tests_passed":0},"raw_output_ref":null,"metadata":{}}
