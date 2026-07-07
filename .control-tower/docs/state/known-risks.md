# Known Risks

- Tower role leakage into direct implementation if delegation discipline is not maintained.
- Memory drift if imported sessions are not curated into docs and working summaries.
- Session ambiguity if Tower sessions are not resumed through `tower resume`.
- Local `main` currently diverges from `origin/main` after the 2026-06-25 rebase; publishing it would rewrite the fork branch and needs explicit user approval.
- Infinigen scenes are procedurally generated; each imported map still needs visual inspection for scale, collision, lighting, and player start placement before data collection.
- `one_bed_apartment` now has complete flythrough MP4s for visual review, but this does not validate interactive collision, scale, lighting, or player-start quality.
- Transient Control Tower runtime artifacts, imported sessions/transcripts, packets, run outputs, and unrelated untracked Unreal scene imports remain intentionally uncommitted after commit `66c7a3106efb46fe0e3904fb344e57651072a2f2`; decide an asset-retention, archive, ignore, or cleanup policy before relying on them as durable project state.
- Dark cafeteria orbit validation passed empirically, but capture render-history/show-flag readback remains unverified in metadata and the editor report could not directly clear map build data; keep luma/frame validation checks visible when applying the workflow to future maps.
- `examples/flashlight/README.md` is outside the configured durable docs harness for the 2026-07-02 Scribe packet and still has an inline active-illumination JSON snippet that omits `"spawn_flashlight": false` for `scene_off_flashlight_off`; keep `docs/` and `examples/flashlight/orbit_light_settings.json` canonical until that README can be refreshed.
- Realistic live cafeteria flashlight runtime validation is blocked until run from a display-capable session: the 2026-07-07 agent attempt crashed during Unreal RHI initialization in a headless shell before map load, warmup, teleop, runtime console-command logs, or visual brightness-stability checks.
