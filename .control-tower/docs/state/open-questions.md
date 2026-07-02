# Open Questions

- Which repo conventions should Scribe treat as canonical?
- Which files or paths should Builder avoid by default?
- What publish workflow should Git-master use if the user explicitly approves pushing the rebased local `main` to `origin/main`?
- What asset-retention policy should apply to generated Unreal scene assets, Tower runtime artifacts, imported sessions/transcripts, packet JSON, and run outputs?

## Resolved Preferences

- Project purpose and Tower routing preferences are recorded in `docs/tower_operating_preferences.md` and `.control-tower/docs/overview.md`.
- Git remote roles are recorded in `docs/tower_operating_preferences.md`: `origin` is the user's fork and `upstream` is `spear-sim/spear`.
