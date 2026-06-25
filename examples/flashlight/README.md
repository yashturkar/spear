# Flashlight

This example launches `SpearSim`, spawns a spotlight, and attaches it to the
current spectator pawn so it stays co-located with your view while you navigate
the scene.

Run it from the repository root:

```console
python examples/flashlight/run.py
```

Use the imported Japanese office map:

```console
python examples/flashlight/run.py --map japanese_office
```

Create or refresh the dark duplicate of the Japanese office map after importing
`Content/JapaneseOffice`:

```console
python tools/run_editor_script.py \
  --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 \
  --script /home/yashturkar/Workspace/spear/examples/flashlight/setup_japanese_office_dark.py \
  --replace-existing-map
```

Cook the dark map into the standalone package:

```console
python tools/run_uat.py \
  --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 \
  --cook-maps /Game/JapaneseOffice/Maps/Demonstration_Dark \
  -cook -stage -package -archive -pak -skipbuild
```

Launch the dark duplicate of the Japanese office map:

```console
python examples/flashlight/run.py --map japanese_office_dark --movement-speed 600
```

Use a slower camera and turn off scene lights so the flashlight dominates:

```console
python examples/flashlight/run.py --map japanese_office --movement-speed 600 --disable-scene-lights
```

Press `Ctrl+C` in the terminal to stop the script and destroy the spawned
flashlight.

## Programmatic Rerun stream

Install the examples extra dependencies before using the Rerun version. The
quoted extra is safe in shells such as zsh:

```console
python -m pip install -e 'python[examples]'
```

Run the live programmatic stream from the repository root:

```console
python examples/flashlight/run_programmatic_rerun.py --map japanese_office_dark --movement-speed 600 --disable-scene-lights
```

The script follows the current live viewport camera instead of a fixed route,
prints compact camera and light status to the terminal, and streams the 2D
image inspection views at `rgb`, `depth_meters`,
`depth_meters_visualization`, and `camera_position_plot`. The RGB stream uses
the final tone curve as opaque RGB, depth is logged as metric depth plus a
normalized RGB preview, and `camera_position_plot` is a matplotlib-rendered
Unreal X/Y game-world plot in meters. The stream does not create a shared
`images` parent, 3D Rerun view, 3D trajectory, or spatial `spear` hierarchy.
Camera world position is logged as non-spatial status scalars under
`status/camera/`, and flashlight enabled state, intensity, yaw offset, pitch
offset, and text status are logged under `status/light/`.
The script sends a fixed Rerun blueprint with separate views for each image
stream and status group, so the viewer should not use the default `/` combined
view.

By default the script spawns Rerun automatically. Pass `--no-rerun-spawn` to
connect manually from an already running Rerun viewer.

Programmatic flashlight control is intended through editing
`compute_light_command` and returning a `LightCommand` in
`examples/flashlight/run_programmatic_rerun.py`. The hook receives elapsed time,
frame index, the current viewport description, and the previous command, so it
can toggle the light, change intensity, or adjust yaw and pitch offsets while
the stream is running.

Live SPEAR/Rerun end-to-end validation remains a user-run check because it
requires a running simulator and Rerun viewer.

## Orbit collection

Use teleop mode to choose a target point and save an orbit specification:

```console
python examples/flashlight/run_orbit_collection.py \
  --mode teleop \
  --map japanese_office_dark \
  --movement-speed 600 \
  --disable-scene-lights \
  --orbit-spec-file examples/flashlight/orbit_spec.json
```

Move the spectator pawn normally. Press `Gamepad_RightShoulder` to select the
point under the camera forward visibility ray; if the ray misses, the script
logs that it used `--fallback-target-distance` centimeters along the camera
forward vector. Press `Gamepad_LeftShoulder` to preview one visible 360
degree orbit around the selected target. After the preview, the script restores
the spectator pawn location and PlayerController control rotation from before
the orbit. The flashlight uses the same toggle key, D-pad aiming, intensity,
cone, and attenuation options as `run.py`.

The orbit spec JSON records the map/map path, start camera pose, selected target
point, orbit radius, duration, FPS, image size, field of view, and baseline
light settings. Render mode reuses that orbit spec and applies each entry in a
light settings JSON list. A reusable three-setting example lives at
`examples/flashlight/light_settings.example.json`:

```json
[
  {
    "name": "baseline_on",
    "enabled": true,
    "intensity": 30000.0,
    "yaw_offset_degrees": 0.0,
    "pitch_offset_degrees": 0.0
  }
]
```

Render RGB and depth visualization videos for every light setting:

```console
python examples/flashlight/run_orbit_collection.py \
  --mode render \
  --orbit-spec-file examples/flashlight/orbit_spec.json \
  --light-settings-file examples/flashlight/light_settings.example.json \
  --output-dir examples/flashlight/orbit_collection_output
```

To render the saved orbit with just `light_on` and `light_off` settings, run:

```console
examples/flashlight/render_orbit_light_on_off.sh
```

Each setting writes PNG frame folders plus two MP4 files:

```text
examples/flashlight/orbit_collection_output/<name>/frames/rgb/
examples/flashlight/orbit_collection_output/<name>/frames/depth_meters_visualization/
examples/flashlight/orbit_collection_output/<name>/rgb.mp4
examples/flashlight/orbit_collection_output/<name>/depth_meters_visualization.mp4
```

The default orbit spec and orbit collection output paths are generated artifacts
and are ignored by Git.

Render a programmatic 10 second flashlight flythrough from fixed camera
waypoints:

```console
python examples/flashlight/render_flythrough.py \
  --duration-seconds 10 \
  --fps 24 \
  --width 1280 \
  --height 720
```

The flythrough writes PNG frames and, when OpenCV has video encoding support,
an MP4:

```text
examples/flashlight/flythrough_output/frames/
examples/flashlight/flythrough_output/flashlight_flythrough.mp4
```

Close other `SpearSim` or flashlight sessions before rendering; SPEAR expects a
single process on its RPC port.

The default flythrough route uses Unreal's navmesh to find collision-aware paths
between coarse floor-level goals, then raises the camera to human height. For
`japanese_office_dark`, edit `ROUTE_GOALS_BY_MAP` in `render_flythrough.py` to
tune the route. Other maps, including `apartment_0000`, sample route goals from
the map navmesh; adjust this with `--num-route-goals`. For debugging, pass
`--route-mode straight` to render direct line segments between fixed goals.

Pass `--render-ground-truth` to save synchronized per-frame outputs in separate
folders:

```console
python examples/flashlight/render_flythrough.py --render-ground-truth
```

This writes RGB, depth, world normals, world positions, diffuse color,
roughness, metallic, specular-for-lighting, material AO, unlit color, object
IDs, and segmentation ID visualizations under `flythrough_output/frames/`. The
MP4 becomes a tiled preview video with subfigures. Add
`--save-raw-ground-truth` to also write exact `.npy` arrays under
`flythrough_output/raw/`.

To build a tiled MP4 from already-rendered frame folders:

```console
python examples/flashlight/make_tiled_video.py
```

This scans `flythrough_output/frames/` and writes
`flythrough_output/flashlight_flythrough_all_modalities.mp4`.

To render aligned RGB frames with and without the onboard flashlight:

```console
python examples/flashlight/render_flythrough.py \
  --map apartment_0000 \
  --duration-seconds 10 \
  --fps 24 \
  --width 1280 \
  --height 720 \
  --render-flashlight-comparison
```

This writes `frames/flashlight_comparison/off/`,
`frames/flashlight_comparison/on/`,
`frames/flashlight_comparison/side_by_side/`, and
`flashlight_comparison.mp4`. The comparison path waits two settle frames after
each flashlight toggle by default; tune this with
`--flashlight-comparison-settle-frames`.
