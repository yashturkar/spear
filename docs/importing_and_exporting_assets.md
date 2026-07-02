# Importing and Exporting Assets

In general, our approach for importing/exporting assets to/from the Unreal Engine is to formulate each import/export task (e.g., import from dataset X, export to destination application Y, etc) as a pipeline consisting of modular stages. We typically implement each pipeline as a directed acyclic graph of stages, and each stage is a Python program that produces and/or consumes data in a user-specified top-level directory for a particular scene. Each stage can optionally access functionality available in the Unreal Editor using the SPEAR API or the editor's built-in Python API. In this document, we demonstrate some example export pipelines that are implemented in this style.

## Assumptions

In order to execute the pipeline in this document, we will assume that you have completed our [Getting Started](getting_started.md) tutorial. We will also assume that you want to execute the pipeline for the `apartment_0000` scene only, and that you want all pipeline output to be generated in a top-level directory called `spear-pipeline`.

## Installing additional Python dependencies

In order to execute the pipeline in this document, you will need to install the `pipeline` optional dependencies. When executing the command below, `PIP_BUILD_CONSTRAINT` forces `pip` to build against the versions we specify in `python/pip_build_constraint.txt`, and `--no-cache-dir` forces a fresh build.

```console
# install additional pipeline dependencies (Windows Powershell)
$env:PIP_BUILD_CONSTRAINT="python/pip_build_constraint.txt"; pip install --no-cache-dir -e "python[pipeline]"

# install additional pipeline dependencies (Windows Command Prompt)
set PIP_BUILD_CONSTRAINT=python/pip_build_constraint.txt && pip install --no-cache-dir -e "python[pipeline]"

# install additional pipeline dependencies (macOS and Linux)
PIP_BUILD_CONSTRAINT=python/pip_build_constraint.txt pip install --no-cache-dir -e "python[pipeline]"
```

## Accessing the Unreal Editor's built-in Python interface

Any pipeline stage that needs to access the Unreal Editor using the editor's built-in Python API can be executed using our `run_editor_script.py` tool, which runs a user-specified script `--script` from within the editor's built-in Python environment. `run_editor_script.py` consumes `--script`, `--unreal-engine-dir`, and several optional arguments such as `--launch-mode` and `--render-offscreen`, and forwards all other arguments directly to the user's script. `--script` must be relative to `spear/pipeline` or absolute. Any path arguments that are forwarded to the user screen must be absolute.

## Maintaining visual parity with Unreal

When executing the pipelines below, specifying the optional `--visual-parity-with-unreal` flag will modify the positions and orientations of meshes to maintain visual parity with the Unreal viewport. This flag is necessary to account for the various coordinate conventions in different viewers.

## Importing an Infinigen indoor scene into SpearSim

The flashlight example includes an editor import script for Infinigen indoor
scenes: `examples/flashlight/setup_infinigen_indoors.py`. The script expects an
Infinigen-exported FBX, imports it as static mesh assets, creates a new Unreal
level, spawns the imported `StaticMesh` assets at the origin with a uniform
scale, adds basic directional and sky lighting plus a `PlayerStart`, saves the
asset directory and map, and logs imported mesh counts plus approximate spawned
mesh bounds.

The commands below show a validated end-to-end workflow for generating an
Infinigen indoor room, exporting it to FBX, importing it into the SpearSim
Unreal project, cooking the map, and running it through the flashlight example.
The absolute paths and conda environment names are local examples from one
validated Linux workstation:

```text
Infinigen repo: /home/yashturkar/Workspace/infinigen
SPEAR repo: /home/yashturkar/Workspace/spear
Unreal Engine: /home/yashturkar/Linux_Unreal_Engine_5.5.4
Infinigen conda env: infinigen
SPEAR conda env: spear-env
```

Adjust these values for your machine. The validated Infinigen setup used
`INFINIGEN_MINIMAL_INSTALL=True`, which is sufficient for Infinigen-Indoors, and
generated a single-room indoor scene with terrain disabled.

### Generate an Infinigen indoor scene

```console
cd /home/yashturkar/Workspace/infinigen
conda activate infinigen

CUDA_VISIBLE_DEVICES=0 python -m infinigen_examples.generate_indoors \
  --seed 0 \
  --task coarse \
  --output_folder outputs/indoors_gpu/coarse \
  -g fast_solve.gin overhead.gin singleroom.gin \
  -p compose_indoors.terrain_enabled=False \
     restrict_solving.solve_max_rooms=1 \
     compose_indoors.invisible_room_ceilings_enabled=True \
     compose_indoors.restrict_single_supported_roomtype=True
```

Optional render preview:

```console
cd /home/yashturkar/Workspace/infinigen
conda activate infinigen

CUDA_VISIBLE_DEVICES=0 python -m infinigen_examples.generate_indoors \
  --seed 0 \
  --task render \
  --input_folder outputs/indoors_gpu/coarse \
  --output_folder outputs/indoors_gpu/frames
```

### Export the Infinigen scene to FBX

```console
cd /home/yashturkar/Workspace/infinigen
conda activate infinigen

python -m infinigen.tools.export \
  --input_folder outputs/indoors_gpu/coarse \
  --output_folder outputs/spear_export \
  -f fbx \
  -r 1024
```

This writes the default FBX consumed by the SPEAR import script:

```text
/home/yashturkar/Workspace/infinigen/outputs/spear_export/export_scene.blend/export_scene.fbx
```

If the export fails, runs out of memory, or produces an FBX that is too large
for a first import, rerun with a lower texture bake resolution:

```console
python -m infinigen.tools.export \
  --input_folder outputs/indoors_gpu/coarse \
  --output_folder outputs/spear_export \
  -f fbx \
  -r 512
```

### Import the FBX into the SpearSim Unreal project

```console
cd /home/yashturkar/Workspace/spear
conda activate spear-env

python tools/run_editor_script.py \
  --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 \
  --launch-mode full \
  --render-offscreen \
  --script /home/yashturkar/Workspace/spear/examples/flashlight/setup_infinigen_indoors.py \
  --fbx-file /home/yashturkar/Workspace/infinigen/outputs/spear_export/export_scene.blend/export_scene.fbx
```

By default, the script writes imported meshes to
`/Game/SPEAR/Scenes/infinigen_indoors_0000/Meshes` and creates the map at
`/Game/SPEAR/Scenes/infinigen_indoors_0000/Maps/infinigen_indoors_0000`. Use
`--mesh-dir` and `--map-path` to target another content location. The script
fails before modifying existing targets unless `--replace-existing-assets` is
provided for an existing mesh directory and `--replace-existing-map` is provided
for an existing map:

```console
python tools/run_editor_script.py \
  --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 \
  --launch-mode full \
  --render-offscreen \
  --script /home/yashturkar/Workspace/spear/examples/flashlight/setup_infinigen_indoors.py \
  --fbx-file /home/yashturkar/Workspace/infinigen/outputs/spear_export/export_scene.blend/export_scene.fbx \
  --replace-existing-assets \
  --replace-existing-map
```

Use `--player-start-x`, `--player-start-y`, `--player-start-z`,
`--player-start-yaw`, and `--actor-scale` to adjust the generated level setup.
Visual quality, scale, collision, lighting, and player start placement should
still be inspected per generated scene.

### Generated world quality checklist

For generated Infinigen worlds intended for active illumination research, use
this checklist before accepting the world as a reusable data-collection map:

- Model real wall openings for windows, not decorative panes on solid walls.
  Include exterior context beyond the opening so windows read correctly from
  inside and can contribute plausible daylight/background cues.
- Add actual Unreal light actors after import for fixtures that should
  illuminate the scene. Do not rely on Blender lights embedded in the FBX
  export; the current import path creates static mesh actors and generic setup
  lights, not fixture-specific Unreal lights.
- Keep materials neutral and desaturated, especially on large surfaces and
  objects likely to be hit by the camera-mounted flashlight. Import materials
  and textures for research-quality worlds unless a deliberate collision or
  geometry-only test justifies `--no-import-materials` and
  `--no-import-textures`.
- Verify furniture orientation in the generated source and in Unreal. Chairs,
  desks, doors, and fixtures should face/use the space as intended before
  spending time on cook or collection runs.
- Enable auto-generated collision for first-pass teleop validation, or record
  an explicit collision plan with simple collision meshes or blocking volumes
  before treating the map as navigable.
- Keep scene complexity and FBX export resolution manageable. Start with
  compact rooms, bounded solve settings, and export resolution `-r 256` or
  `-r 512`; raise resolution only after import, cook, and runtime validation
  are healthy.
- Produce a validation report after import that records the map path, mesh
  asset count, static mesh actor count, light actor/component counts, and
  approximate spawned bounds. Treat missing bounds, unexpectedly low mesh
  counts, or missing fixture lights as blockers.
- Cook/package the target map and launch the packaged runtime before calling
  the world usable. A successful editor import alone is not enough for data
  collection.
- Run live flashlight validation in the simulator. Check spawn placement,
  scale, collision, fixture visibility, material response, and flashlight-only
  behavior from the actual camera/controller path.

Lighting balance should be tuned at launch per world. Prefer
`--scene-light-intensity-scale` to dim existing scene lights while keeping
fixture context enabled; it defaults to `1.0`, accepts finite non-negative
values, and `0.0` dims scene lights to off without using
`--disable-scene-lights`. For small rooms, keep the spawned co-located
flashlight from flooding Lumen indirect bounce with
`--indirect-lighting-intensity 0`, then tune `--intensity`,
`--attenuation-radius`, `--inner-cone-angle`, and `--outer-cone-angle` for the
world.

The flashlight validation entry points run with fixed exposure by default by
launching the renderer with `r.DefaultFeature.AutoExposure=False` and
`r.EyeAdaptationQuality=0`. This matters when validating scene-light scaling:
with eye adaptation enabled, Unreal can normalize the final tone-mapped view so
different `--scene-light-intensity-scale` values look similar even when the
light components were scaled correctly. Pass `--enable-auto-exposure` only when
you want the map's normal adaptive exposure behavior.

The cafeteria v2 starting point is:

```console
python examples/flashlight/run.py \
  --map-path /Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2 \
  --movement-speed 600 \
  --scene-light-intensity-scale 0.2 \
  --intensity 1500 \
  --attenuation-radius 450 \
  --inner-cone-angle 8 \
  --outer-cone-angle 20 \
  --indirect-lighting-intensity 0
```

For the next live validation pass, compare the same camera pose at fixed
exposure with `--scene-light-intensity-scale 0.2`, `0.1`, and `0.0` before
falling back to `--disable-scene-lights`.

For orbit captures that require a near-black scene-off control, the validated
dark cafeteria map variant is:

```text
/Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2_flashlight_validation_dark
```

This variant was created from `cafeteria_500sqft_v2` for flashlight validation
by hiding residual exterior/window/fixture-emissive contributors, making the
eight light components movable, and setting `force_no_precomputed_lighting`
with readback true. Its 2026-07-01 cook/package and orbit render validation
passed the `scene_off_flashlight_off` acceptance check: median mean luma was
`0.0` against the `20.0` threshold, the control never spawned or enabled a
flashlight, and the paired `scene_off_flashlight_on` run showed localized
flashlight illumination rather than scene-wide residual lighting. The editor
report could not directly clear `map_build_data`, and orbit metadata still
reports unverified capture render-history/show-flag readback, so retain the
run logs and luma summary as the empirical acceptance record for this variant.

### Cook and run the imported map

After the map is imported and saved, cook it into the SpearSim standalone
package:

```console
cd /home/yashturkar/Workspace/spear
conda activate spear-env

python tools/run_uat.py \
  --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 \
  --cook-maps /Game/SPEAR/Scenes/infinigen_indoors_0000/Maps/infinigen_indoors_0000 \
  -cook -stage -package -archive -pak -skipbuild
```

If the standalone executable has not been built yet, use `-build` instead of
`-skipbuild`. After changing the imported Unreal assets or map, rerun the cook
step with `-cook`.

Then run the cooked map through the flashlight example:

```console
cd /home/yashturkar/Workspace/spear
conda activate spear-env

python examples/flashlight/run.py \
  --map-path /Game/SPEAR/Scenes/infinigen_indoors_0000/Maps/infinigen_indoors_0000 \
  --movement-speed 600
```

Add `--disable-scene-lights` when you want the flashlight to dominate the
lighting for active-illumination inspection.

This workflow was validated on 2026-06-25: FBX export completed, the Unreal
editor import validated imported mesh assets and
`/Game/SPEAR/Scenes/infinigen_indoors_0000/Maps/infinigen_indoors_0000`, the
cook/build step succeeded, and the user confirmed the cooked map runs with
`examples/flashlight/run.py`.

### Validated one-bedroom apartment import profile

The same import script has also been validated for a larger one-bedroom
Infinigen scene generated from a floorplan. This run targeted the map
`/Game/SPEAR/Scenes/one_bed_apartment/Maps/one_bed_apartment` and replaced the
corresponding mesh directory at
`/Game/SPEAR/Scenes/one_bed_apartment/Meshes`.

The validated 2026-06-26 generation used seed `21`, the original
`one_bed_floorplan.json`, and a lighter solve profile:

```console
python -m infinigen_examples.generate_indoors \
  --seed 21 \
  --task coarse \
  --output_folder /home/yashturkar/Workspace/infinigen/outputs/one_bed_apartment_spear_light/coarse \
  -g fast_solve.gin \
  -p compose_indoors.terrain_enabled=False \
     compose_indoors.invisible_room_ceilings_enabled=True \
     compose_indoors.solve_small_enabled=False \
     compose_indoors.solve_steps_large=80 \
     compose_indoors.solve_steps_medium=30 \
     Solver.floor_plan="'/home/yashturkar/Workspace/infinigen/outputs/one_bed_apartment/one_bed_floorplan.json'"
```

The exported scene used FBX resolution `-r 256`, producing a `746M` FBX. The
coarse scene reported `19,733,377` tris in `polycounts.txt`, substantially
smaller than the prior heavy run's `72,943,949` tris.

For this larger scene, the successful Unreal import disabled expensive optional
asset import work:

```console
python tools/run_editor_script.py \
  --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 \
  --launch-mode full \
  --render-offscreen \
  --script /home/yashturkar/Workspace/spear/examples/flashlight/setup_infinigen_indoors.py \
  --fbx-file /home/yashturkar/Workspace/infinigen/outputs/one_bed_apartment_spear_light/spear_export_r256/export_scene.blend/export_scene.fbx \
  --mesh-dir /Game/SPEAR/Scenes/one_bed_apartment/Meshes \
  --map-path /Game/SPEAR/Scenes/one_bed_apartment/Maps/one_bed_apartment \
  --replace-existing-assets \
  --replace-existing-map \
  --no-auto-generate-collision \
  --no-import-materials \
  --no-import-textures
```

The import completed with `111` static mesh assets and `111` spawned static
mesh actors. Cooking, staging, packaging, archiving, and PAK generation
succeeded with:

```console
python tools/run_uat.py \
  --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 \
  --cook-maps /Game/SPEAR/Scenes/one_bed_apartment/Maps/one_bed_apartment \
  -cook -stage -package -archive -pak -skipbuild
```

The resulting map is ready for flashlight runtime inspection:

```console
python examples/flashlight/run.py \
  --map-path /Game/SPEAR/Scenes/one_bed_apartment/Maps/one_bed_apartment \
  --movement-speed 600
```

As of the validated import, visual quality, scale, lighting, collision
behavior, and `PlayerStart` usability had not yet been interactively checked in
the simulator. Automated flythrough generation was later validated for this
map, but that does not replace interactive inspection of collision and spawn
quality.

### Validated college classroom import profile

The same script has also been validated for a compact `college_classroom`
Infinigen scene. This run targeted
`/Game/SPEAR/Scenes/college_classroom/Maps/college_classroom` and wrote meshes
under `/Game/SPEAR/Scenes/college_classroom/Meshes`.

The validated 2026-06-30 import used an existing generated scene at
`/home/yashturkar/Workspace/infinigen/outputs/college_classroom/coarse` and
exported it to FBX at resolution `-r 256`:

```console
python -m infinigen.tools.export \
  --input_folder /home/yashturkar/Workspace/infinigen/outputs/college_classroom/coarse \
  --output_folder /home/yashturkar/Workspace/infinigen/outputs/college_classroom/spear_export_r256 \
  -f fbx \
  -r 256
```

The exported FBX was `5.8M` and was imported with collision generation,
material import, and texture import disabled:

```console
python tools/run_editor_script.py \
  --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 \
  --launch-mode full \
  --render-offscreen \
  --script /home/yashturkar/Workspace/spear/examples/flashlight/setup_infinigen_indoors.py \
  --fbx-file /home/yashturkar/Workspace/infinigen/outputs/college_classroom/spear_export_r256/export_scene.blend/export_scene.fbx \
  --mesh-dir /Game/SPEAR/Scenes/college_classroom/Meshes \
  --map-path /Game/SPEAR/Scenes/college_classroom/Maps/college_classroom \
  --replace-existing-assets \
  --replace-existing-map \
  --no-auto-generate-collision \
  --no-import-materials \
  --no-import-textures
```

The import completed with `285` static mesh assets and `285` spawned static
mesh actors. Reported spawned bounds were min `(-520.00, -424.00, -8.00)`, max
`(520.00, 425.75, 308.00)`, and dimensions `(1040.00, 849.75, 316.00)`.
Unreal emitted no-smoothing-group warnings for the imported FBX meshes, but the
import completed and `AssetCheck` validation reached the college classroom mesh
assets and map.

Cooking, staging, packaging, archiving, and PAK generation succeeded with:

```console
python tools/run_uat.py \
  --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 \
  --cook-maps /Game/SPEAR/Scenes/college_classroom/Maps/college_classroom \
  -cook -stage -package -archive -pak -skipbuild
```

The resulting map is ready for flashlight runtime inspection:

```console
python examples/flashlight/run.py \
  --map-path /Game/SPEAR/Scenes/college_classroom/Maps/college_classroom \
  --movement-speed 600
```

As of the validated import and cook, visual quality, scale, lighting, collision
behavior, and `PlayerStart` usability had not yet been interactively checked in
the simulator.

## Exporting to MuJoCo

```console
# generate Unreal metadata
python tools/run_editor_script.py --unreal-engine-dir path/to/UE_5.5 --launch-mode full --render-offscreen --script export_unreal_metadata/run.py --export-dir path/to/spear-pipeline/scenes/apartment_0000

# generate Unreal geometry
python tools/run_editor_script.py --unreal-engine-dir path/to/UE_5.5 --launch-mode full --render-offscreen --script export_unreal_geometry.py --export-dir path/to/spear-pipeline/scenes/apartment_0000

# visualize Unreal geometry (optional)
python pipeline/visualize_unreal_geometry.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000 --visual-parity-with-unreal --ignore-actors Meshes/22_ceiling/Ceiling

# generate a compact kinematic tree scene representation
python pipeline/generate_kinematic_trees.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000

# visualize the compact kinematic tree scene representation (optional)
python pipeline/visualize_kinematic_trees.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000

# generate optimized collision geometry
python pipeline/generate_collision_geometry.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000

# visualize the collision geometry (optional)
python pipeline/visualize_collision_geometry.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000

# generate a MuJoCo scene
python pipeline/generate_mujoco_scene.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000 --mujoco-model-name apartment_0000 --visual-parity-with-unreal --ignore-actors Meshes/22_ceiling/Ceiling --color-mode unique_color_per_body

# interactively browse the MuJoCo scene using the default MuJoCo viewer (optional)
python -m mujoco.viewer --mjcf=path/to/spear-pipeline/scenes/apartment_0000/mujoco_scene/main.mjcf
```

## Generating flythrough videos

For imported maps, cook the target map into the standalone package before
running the runtime camera-keyframe, image, or video stages. If a standalone
launch fails with a missing map package, rerun the cook step with the exact
map path:

```console
python tools/run_uat.py \
  --unreal-engine-dir path/to/UE_5.5 \
  --cook-maps /Game/SPEAR/Scenes/one_bed_apartment/Maps/one_bed_apartment \
  -cook -stage -package -archive -pak -skipbuild
```

The runtime `user_config.yaml` used by the camera keyframe and image stages
should point `SPEAR.INSTANCE.GAME_EXECUTABLE` at the packaged standalone
executable, set `SP_SERVICES.INITIALIZE_ENGINE_SERVICE.GAME_DEFAULT_MAP` to
the map being rendered, and use a fixed delta time when deterministic video
timing is needed. On the validated Linux workstation, the successful
`one_bed_apartment` run used the `Standalone-Development/Linux/SpearSim.sh`
executable without the `renderoffscreen` command-line argument and included
empty legacy `SP_CORE.*_INI_CONFIG_VALUES` maps for compatibility with the
available standalone binary.

```console
# generate Unreal metadata
python tools/run_editor_script.py --unreal-engine-dir path/to/UE_5.5 --launch-mode full --render-offscreen --script export_unreal_metadata/run.py --export-dir path/to/spear-pipeline/scenes/apartment_0000

# generate Unreal geometry (only required to support the optional visualization steps below)
python tools/run_editor_script.py --unreal-engine-dir path/to/UE_5.5 --launch-mode full --render-offscreen --script export_unreal_geometry.py --export-dir path/to/spear-pipeline/scenes/apartment_0000

# generate free-space points
python pipeline/generate_free_space_points.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000

# visualize the free-space points (optional)
python pipeline/visualize_free_space_points.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000 --visual-parity-with-unreal --ignore-actors Meshes/22_ceiling/Ceiling

# generate a visibility graph between free-space points
python pipeline/generate_free_space_visibility_graph.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000

# visualize the visibility graph (optional)
python pipeline/visualize_free_space_visibility_graph.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000 --visual-parity-with-unreal --ignore-actors Meshes/22_ceiling/Ceiling

# generate free-space bounding boxes that cover the free-space points
python pipeline/generate_free_space_bounding_boxes.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000

# visualize the free-space bounding boxes (optional)
python pipeline/visualize_free_space_bounding_boxes.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000 --visual-parity-with-unreal --ignore-actors Meshes/22_ceiling/Ceiling

# generate smooth paths through the free space
python pipeline/generate_free_space_paths.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000

# visualize the smooth paths (optional)
python pipeline/visualize_free_space_paths.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000 --visual-parity-with-unreal --ignore-actors Meshes/22_ceiling/Ceiling

# generate camera keyframes that include orientations along each path
python pipeline/generate_free_space_camera_keyframes.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000 --user-config-files path/to/user_config.yaml --view-selection-mode argmax

# visualize the camera keyframes (optional)
python pipeline/visualize_free_space_camera_keyframes.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000 --visual-parity-with-unreal --ignore-actors Meshes/22_ceiling/Ceiling

# generate camera paths that include orientations
python pipeline/generate_free_space_camera_paths.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000

# visualize the camera paths (optional)
python pipeline/visualize_free_space_camera_paths.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000 --visual-parity-with-unreal --ignore-actors Meshes/22_ceiling/Ceiling

# generate rendered images along each camera path
python pipeline/generate_free_space_camera_path_images.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000 --user-config-files path/to/user_config.yaml

# generate rendered videos
python pipeline/generate_free_space_camera_path_videos.py --pipeline-dir path/to/spear-pipeline/scenes/apartment_0000
```

### Validated one-bedroom apartment flythrough

On 2026-06-30, the flythrough pipeline generated two complete videos for
`/Game/SPEAR/Scenes/one_bed_apartment/Maps/one_bed_apartment` under:

```text
/home/yashturkar/Workspace/spear-pipeline/scenes/one_bed_apartment_flythrough_20260630T184150Z
```

Both final MP4s were validated at `1920x1080`, `30` FPS, `1000` frames, and
`33.33` seconds. The selected review pick was
`free_space_camera_path_videos/final/0000.mp4` because it was complete and had
the larger encoded size plus a more varied contact-sheet inspection than
`0001.mp4`. The same directory contains the contact sheets, intermediate H5
files, generated configs, runner scripts, and per-stage logs needed to
reproduce or debug the run.
