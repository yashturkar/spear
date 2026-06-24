# Current Status

- Control Tower bootstrap initialized.
- Graph-backed memory is enabled through `.control-tower/state/decision-graph/`.
- Project purpose recorded: spear is for building and setting up a simulator for active illumination research.
- Tower should operate lean by default: quick discussion, Builder implements, user runs the simulator to check.
- Inspector is not a default route; use only for requested review/QA or high-risk changes.
- Scout is reserved for research during deep technical discussions.
- As of Git-master result `git-master-2e497ca4-5a09-4097-8c57-200b340cfb01-result`, local commit `02c5ec68e0f00aabe3b293c69b88fc5d42093e9f` accepted the current flashlight/Rerun state and left `main` clean, ahead of `origin/main` by two commits, with no push performed.
- Durable docs already describe the accepted flashlight/Rerun workflow in `docs/running_our_example_applications.md` and `examples/flashlight/README.md`: top-level `rgb`, `depth_meters`, `depth_meters_visualization`, and `camera_position_plot` streams; non-spatial `status/camera/*` and `status/light/*`; fixed Rerun blueprint views; no shared `images` parent or 3D/spatial `spear` hierarchy.
- As of Git-master result `git-master-d68b03c4-37ef-4039-bd0b-0edab3c15ba6-result`, local commit `2df1204fe29175ba0771570cc7fb080d6847f45a` added the flashlight orbit collection workflow: `examples/flashlight/run_orbit_collection.py`, `examples/flashlight/light_settings.example.json`, validation tests, README coverage, and ignored generated orbit spec/output paths. Durable docs now summarize the workflow in `docs/running_our_example_applications.md`.
- Live SPEAR/Rerun simulator validation remains a user-run check.
