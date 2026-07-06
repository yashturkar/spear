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

The flashlight entry points disable Unreal auto exposure / eye adaptation by
default so launch-time scene-light scale changes are visible instead of being
normalized by exposure adaptation. Pass `--enable-auto-exposure` only when you
want the map's normal adaptive exposure behavior.

Use a slower camera and dim the cafeteria v2 fixture lights so the co-located
flashlight is visible while the real indoor lights stay enabled:

```console
python examples/flashlight/run.py \
  --map-path /Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2 \
  --movement-speed 600 \
  --disable-auto-exposure \
  --scene-light-intensity-scale 0.2 \
  --intensity 1200 \
  --attenuation-radius 650 \
  --inner-cone-angle 2 \
  --outer-cone-angle 60 \
  --source-radius 12 \
  --soft-source-radius 80 \
  --indirect-lighting-intensity 0
```

For small interiors with saturated nearby surfaces, keep direct flashlight
bounce out of Lumen indirect lighting and dim scene fixtures instead of
disabling them:

```console
python examples/flashlight/run.py \
  --map-path /Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2 \
  --movement-speed 600 \
  --disable-auto-exposure \
  --scene-light-intensity-scale 0.1 \
  --intensity 1200 \
  --attenuation-radius 650 \
  --inner-cone-angle 2 \
  --outer-cone-angle 60 \
  --source-radius 12 \
  --soft-source-radius 80 \
  --indirect-lighting-intensity 0
```

For fixed-exposure brightness validation, compare the same camera position
across scene-light scales:

```console
python examples/flashlight/run.py \
  --map-path /Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2 \
  --movement-speed 600 \
  --disable-auto-exposure \
  --scene-light-intensity-scale 0.2 \
  --intensity 1200 \
  --attenuation-radius 650 \
  --inner-cone-angle 2 \
  --outer-cone-angle 60 \
  --source-radius 12 \
  --soft-source-radius 80 \
  --indirect-lighting-intensity 0

python examples/flashlight/run.py \
  --map-path /Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2 \
  --movement-speed 600 \
  --disable-auto-exposure \
  --scene-light-intensity-scale 0.1 \
  --intensity 1200 \
  --attenuation-radius 650 \
  --inner-cone-angle 2 \
  --outer-cone-angle 60 \
  --source-radius 12 \
  --soft-source-radius 80 \
  --indirect-lighting-intensity 0

python examples/flashlight/run.py \
  --map-path /Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2 \
  --movement-speed 600 \
  --disable-auto-exposure \
  --scene-light-intensity-scale 0.0 \
  --intensity 1200 \
  --attenuation-radius 650 \
  --inner-cone-angle 2 \
  --outer-cone-angle 60 \
  --source-radius 12 \
  --soft-source-radius 80 \
  --indirect-lighting-intensity 0
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

Use the workflow helper to choose a target point and save an orbit
specification:

```console
examples/flashlight/run_orbit_workflow.sh teleop
```

Move the spectator pawn normally. Press `Gamepad_RightShoulder` to select the
point under the camera forward visibility ray; if the ray misses, the script
logs that it used `--fallback-target-distance` centimeters along the camera
forward vector. Press `Gamepad_LeftShoulder` to preview one visible 360
degree orbit around the selected target. After the preview, the script restores
the spectator pawn location and PlayerController control rotation from before
the orbit. The flashlight uses the same toggle key, D-pad aiming, intensity,
cone, attenuation, and indirect lighting options as `run.py`.

The helper defaults to the cafeteria v2 map path,
`examples/flashlight/orbit_spec.json`,
`examples/flashlight/orbit_light_settings.json`, and
`examples/flashlight/orbit_collection_output`. It passes fixed exposure
explicitly with `--disable-auto-exposure`, scales scene lights with
`--scene-light-intensity-scale 0.2`, leaves scene-capture render history
disabled by the Python script default, and uses the current small-room
flashlight profile:
`--intensity 1200`, `--attenuation-radius 650`,
`--inner-cone-angle 2`, `--outer-cone-angle 60`,
`--source-radius 12`, `--soft-source-radius 80`, and
`--indirect-lighting-intensity 0`. Override these with matching helper flags or
environment variables such as `SPEAR_SCENE_LIGHT_INTENSITY_SCALE=0.1`,
`SPEAR_FLASHLIGHT_SOURCE_RADIUS=12`, or
`SPEAR_FLASHLIGHT_SOFT_SOURCE_RADIUS=80`.

The orbit spec JSON records the map/map path, start camera pose, selected target
point, orbit radius, duration, FPS, image size, field of view, and baseline
light settings. Render mode reuses that orbit spec and applies each entry in a
light settings JSON list. The checked-in active-illumination set lives at
`examples/flashlight/orbit_light_settings.json`:

```json
[
  {
    "name": "scene_on_flashlight_off",
    "scene_lights_enabled": true,
    "enabled": false,
    "intensity": 0.0,
    "yaw_offset_degrees": 0.0,
    "pitch_offset_degrees": 0.0
  },
  {
    "name": "scene_off_flashlight_off",
    "scene_lights_enabled": false,
    "spawn_flashlight": false,
    "enabled": false,
    "intensity": 0.0,
    "yaw_offset_degrees": 0.0,
    "pitch_offset_degrees": 0.0
  },
  {
    "name": "scene_off_flashlight_on",
    "scene_lights_enabled": false,
    "enabled": true,
    "intensity": 1200.0,
    "yaw_offset_degrees": 0.0,
    "pitch_offset_degrees": 0.0
  },
  {
    "name": "scene_on_flashlight_on",
    "scene_lights_enabled": true,
    "enabled": true,
    "intensity": 1200.0,
    "yaw_offset_degrees": 0.0,
    "pitch_offset_degrees": 0.0
  }
]
```

Render RGB and depth videos for every light setting:

```console
examples/flashlight/run_orbit_workflow.sh render
```

The default `color-flashlight-only` render preset writes temporary settings and
runs two color passes against the dark cafeteria validation map. The scene-on
pass uses the configured `--scene-light-intensity-scale`; the scene-off pass
keeps the RGB capture on `final_tone_curve_hdr` and forces
`--scene-light-intensity-scale 0.0`, preserving material color while removing
runtime scene light contribution. The default render command therefore writes
exactly these active-illumination conditions: `scene_on_flashlight_off`,
`scene_on_flashlight_on`, `scene_off_flashlight_off`, and
`scene_off_flashlight_on`. Use `--render-preset validation` to render the
checked-in `examples/flashlight/orbit_light_settings.json` diagnostic path,
including its scene-off lighting-only capture settings. The scene-off
flashlight-off output is a diagnostic control for baked, static, or environment
illumination that can remain after runtime scene lights are removed. Render mode
marks each explicit capture as a camera cut by default, disables capture
render-state persistence, and turns off Lumen GI/reflections, screen-space
reflections, Temporal AA, and motion blur for deterministic data collection;
pass
`examples/flashlight/run_orbit_workflow.sh render -- --enable-render-history`
only when comparing against the engine's normal temporal behavior.

To render the saved orbit with just `light_on` and `light_off` settings, run:

```console
examples/flashlight/render_orbit_light_on_off.sh
```

Each setting writes PNG frame folders, raw metric depth arrays, and MP4 files:

```text
examples/flashlight/orbit_collection_output/<name>/frames/rgb/
examples/flashlight/orbit_collection_output/<name>/frames/depth_meters_npy/
examples/flashlight/orbit_collection_output/<name>/frames/depth_meters_viridis/
examples/flashlight/orbit_collection_output/<name>/rgb.mp4
examples/flashlight/orbit_collection_output/<name>/depth_meters_viridis.mp4
examples/flashlight/orbit_collection_output/<name>/metadata.json
```

With the default helper settings, the MP4 files land at:

```text
examples/flashlight/orbit_collection_output/scene_on_flashlight_off/rgb.mp4
examples/flashlight/orbit_collection_output/scene_on_flashlight_off/depth_meters_viridis.mp4
examples/flashlight/orbit_collection_output/scene_off_flashlight_off/rgb.mp4
examples/flashlight/orbit_collection_output/scene_off_flashlight_off/depth_meters_viridis.mp4
examples/flashlight/orbit_collection_output/scene_off_flashlight_on/rgb.mp4
examples/flashlight/orbit_collection_output/scene_off_flashlight_on/depth_meters_viridis.mp4
examples/flashlight/orbit_collection_output/scene_on_flashlight_on/rgb.mp4
examples/flashlight/orbit_collection_output/scene_on_flashlight_on/depth_meters_viridis.mp4
```

Depth `.npy` frames store raw metric depth. Viridis PNGs and depth videos use
one stable color range per light setting, but the default range is clipped to
the 1st and 99th percentiles of finite metric depth samples so huge far-plane
values or other outliers do not flatten the useful orbit contrast. This affects
only the PNG/MP4 visualization outputs. Adjust the clipping with
`--depth-visualization-lower-percentile` and
`--depth-visualization-upper-percentile`, or force explicit bounds with
`--depth-visualization-min-meters` and `--depth-visualization-max-meters`.

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
