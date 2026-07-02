# Known Risks

- Tower role leakage into direct implementation if delegation discipline is not maintained.
- Memory drift if imported sessions are not curated into docs and working summaries.
- Session ambiguity if Tower sessions are not resumed through `tower resume`.
- Local `main` currently diverges from `origin/main` after the 2026-06-25 rebase; publishing it would rewrite the fork branch and needs explicit user approval.
- Infinigen scenes are procedurally generated; each imported map still needs visual inspection for scale, collision, lighting, and player start placement before data collection.
- `one_bed_apartment` now has complete flythrough MP4s for visual review, but this does not validate interactive collision, scale, lighting, or player-start quality.
- Generated Unreal scene assets, Tower runtime artifacts, imported sessions/transcripts, packets, and runs remain intentionally uncommitted after the 2026-07-01 cafeteria/flashlight check-in; decide an asset-retention, archive, ignore, or cleanup policy before relying on them as durable project state.
- Dark cafeteria orbit validation passed empirically, but capture render-history/show-flag readback remains unverified in metadata and the editor report could not directly clear map build data; keep luma/frame validation checks visible when applying the workflow to future maps.
