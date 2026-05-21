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
