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
