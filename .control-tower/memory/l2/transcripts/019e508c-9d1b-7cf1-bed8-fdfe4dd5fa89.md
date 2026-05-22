## User

# Builder

You are Builder, the implementation specialist for this repository.

## Responsibilities

- Write and modify product code within the assigned scope.
- Add or update tests when appropriate.
- Report all changed artifacts clearly.
- Flag documentation and review implications.

## Restrictions

- Stay within the TaskPacket scope.
- Do not silently redesign architecture outside the task.
- Do not perform Git actions unless explicitly included and clearly safe.
- Return a ResultPacket only.

## Policy

```yaml
agent: Builder
role: implementation
allowed_paths:
  - src/
  - tests/
  - .control-tower/
prohibited_actions:
  - force push
  - unrelated refactors
  - architecture changes without escalation
```

## Task Packet

```json
{
  "schema_version": "1.0.0",
  "packet_type": "task",
  "packet_id": "31b4ed5a-e275-4b59-8b00-a71f56ed6c97",
  "trace_id": "886c43e9-b5a0-4294-b464-62e122c03b95",
  "parent_packet_id": null,
  "created_at": "2026-05-22T16:37:26Z",
  "from_agent": "tower",
  "to_agent": "builder",
  "task_type": "implementation",
  "priority": "high",
  "project_id": "spear",
  "session_id": "tower-session",
  "title": "Simplify Rerun stream to RGB/depth only and remove 3D view",
  "objective": "Update the programmatic flashlight Rerun example so it only publishes accepted 2D image streams and non-spatial status, removing world-normal/diffuse streams and all 3D/spatial Rerun logging.",
  "instructions": [
    "Keep these image streams: images/rgb, images/depth_meters, images/depth_meters_visualization.",
    "Remove these image streams and associated capture/components/helpers if no longer needed: images/world_normal_visualization and images/diffuse_color_visualization.",
    "Remove the 3D Rerun view/spatial logging entirely: no spear ViewCoordinates root, no Transform3D, no Pinhole/frustum, no spear/camera/rgb_projection, no Points3D, no LineStrips3D, no Arrows3D.",
    "Keep useful non-spatial Rerun status/scalars for light enabled/intensity/yaw/pitch and camera world position if already available, but place them outside the spatial spear tree, for example status/light/* and status/camera/*.",
    "Keep terminal status printing.",
    "Update README and running guide to describe the reduced Rerun output."
  ],
  "constraints": [
    "Do not remove programmatic light control.",
    "Do not run live simulator-dependent commands."
  ],
  "inputs": {
    "files": [
      "examples/flashlight/run_programmatic_rerun.py",
      "examples/flashlight/README.md",
      "docs/running_our_example_applications.md"
    ],
    "artifacts": [],
    "references": []
  },
  "expected_outputs": [
    "Patched script and docs with RGB/depth-only 2D Rerun stream and no spatial 3D logging."
  ],
  "definition_of_done": [
    "python -m py_compile examples/flashlight/run_programmatic_rerun.py passes.",
    "Static check confirms no world_normal/diffuse Rerun streams and no 3D archetypes Transform3D, Pinhole, Points3D, LineStrips3D, or Arrows3D remain in the script.",
    "ResultPacket lists final Rerun paths."
  ],
  "memory_context_refs": [],
  "doc_context_refs": [],
  "time_budget": {
    "soft_seconds": 900,
    "hard_seconds": 3600
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

{"schema_version":"1.0.0","packet_type":"result","packet_id":"builder-progress-31b4ed5a-e275-4b59-8b00-a71f56ed6c97","trace_id":"886c43e9-b5a0-4294-b464-62e122c03b95","parent_packet_id":"31b4ed5a-e275-4b59-8b00-a71f56ed6c97","created_at":"2026-05-22T16:40:00Z","from_agent":"builder","to_agent":"tower","status":"partial","summary":"Applying the scoped script/docs changes now: removing the extra capture components and replacing spatial Rerun logs with top-level image streams plus status/* scalars/text.","work_completed":[],"artifacts_changed":[],"artifacts_created":[],"artifacts_deleted":[],"findings":[],"follow_up_recommendations":[],"review_requested":false,"doc_update_needed":false,"memory_worthy":[],"metrics":{"tokens_used":0,"files_touched":0,"tests_added":0,"tests_passed":0},"raw_output_ref":null,"metadata":{}}

## Agent

{"schema_version":"1.0.0","packet_type":"result","packet_id":"builder-31b4ed5a-e275-4b59-8b00-a71f56ed6c97-result","trace_id":"886c43e9-b5a0-4294-b464-62e122c03b95","parent_packet_id":"31b4ed5a-e275-4b59-8b00-a71f56ed6c97","created_at":"2026-05-22T16:39:58Z","from_agent":"builder","to_agent":"tower","status":"success","summary":"Simplified the programmatic flashlight Rerun example to RGB/depth-only 2D streams plus non-spatial status. Final Rerun paths are images/rgb, images/depth_meters, images/depth_meters_visualization, status/camera/world_x_meters, status/camera/world_y_meters, status/camera/world_z_meters, status/camera/status, status/light/intensity, status/light/enabled, status/light/yaw_offset_degrees, status/light/pitch_offset_degrees, and status/light/status.","work_completed":["Reduced capture components to rgb and depth_meters only.","Removed world normal and diffuse image streams and their conversion helpers from run_programmatic_rerun.py.","Removed all spatial/3D Rerun logging from run_programmatic_rerun.py, including the spear root ViewCoordinates, camera Transform3D/Pinhole, rgb_projection, Points3D, LineStrips3D, and Arrows3D.","Kept terminal status printing and programmatic light control unchanged.","Moved Rerun light and camera telemetry to non-spatial status/camera/* and status/light/* paths.","Updated examples/flashlight/README.md and docs/running_our_example_applications.md to describe the reduced Rerun output."],"artifacts_changed":["examples/flashlight/run_programmatic_rerun.py","examples/flashlight/README.md","docs/running_our_example_applications.md"],"artifacts_created":[],"artifacts_deleted":[],"findings":[{"severity":"info","message":"python -m py_compile examples/flashlight/run_programmatic_rerun.py passed."},{"severity":"info","message":"Static rg check found no remaining world_normal, diffuse, Transform3D, Pinhole, Points3D, LineStrips3D, Arrows3D, ViewCoordinates, rgb_projection, spear/camera, spear/light, camera_trajectory, or camera_position references in examples/flashlight/run_programmatic_rerun.py."},{"severity":"warning","message":"Live SPEAR/Rerun end-to-end validation was not run because simulator-dependent commands are prohibited by the task constraints."}],"follow_up_recommendations":["Inspector review is requested because the TaskPacket requires review."],"review_requested":true,"doc_update_needed":false,"memory_worthy":[],"metrics":{"tokens_used":0,"files_touched":3,"tests_added":0,"tests_passed":2},"raw_output_ref":null,"metadata":{}}
