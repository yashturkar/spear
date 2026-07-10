# Running our Example Applications

## Assumptions

We will assume that you have completed all the steps in our [Getting Started](docs/getting_started.md) tutorial.

## Installing additional Python dependencies

In order to execute the examples in this document, you will need to install several additional Python dependencies.

```console
pip install -e "python[examples]"
```

## Configuring the behavior of the `spear` Python package

In typical use cases, you will need to configure the behavior of the `spear` Python package before you interact with it. In each of our example applications, we include a configuration file named `user_config.yaml.example` to use as a starting point. To run each example application, you must rename this file to `user_config.yaml` and modify the contents appropriately for your system. At a minimum, you will need to set the `SPEAR.INSTANCE.GAME_EXECUTABLE` parameter to the location of your `SpearSim` executable. Depending on your platform, the path to your executable should be formatted as follows.

```
Windows: path\\to\\Windows\\SpearSim.exe
macOS:   path/to/Mac/SpearSim.app
Linux:   path/to/Linux/SpearSim.sh
```

Your `user_config.yaml` file only needs to specify the value of a parameter if it differs from the defaults defined in the `python/spear/config` directory. You can browse this directory for a complete set of all user-configurable parameters.

If you're running on Linux, you may need to set the `SPEAR.ENVIRONMENT_VARS.VK_ICD_FILENAMES` parameter to an appropriate value for your specific hardware setup. This parameter only has an effect on Linux, and is used to force the Vulkan runtime to load a vendor-specific GPU driver by setting the `VK_ICD_FILENAMES` environment variable. This parameter may or may not be necessary, depending on your specific hardware setup. If you have already set the `VK_ICD_FILENAMES` environment variable before interacting with the `spear` Python package, you do not need to specify `SPEAR.ENVIRONMENT_VARS.VK_ICD_FILENAMES`. If you have an NVIDIA GPU, you probably need to set `SPEAR.ENVIRONMENT_VARS.VK_ICD_FILENAMES` to `/usr/share/vulkan/icd.d/nvidia_icd.json`.

## Running an example application

You are now ready to run an example application.

```console
python examples/getting_started/run.py
```

We recommend browsing through our example applications to get a sense of what is currently possible with SPEAR.
  - [`examples/control_car`](../examples/control_car) demonstrates how to control the default Unreal car.
  - [`examples/control_character`](../examples/control_character) demonstrates how to control the default Unreal humanoid character.
  - [`examples/control_city_sample`](../examples/control_city_sample) demonstrates how to control Epic Games' `CitySample` project.
  - [`examples/control_cropout_sample`](../examples/control_cropout_sample) demonstrates how to control Epic Games' `CropoutSample` project.
  - [`examples/control_editor`](../examples/control_editor) demonstrates how to control the Unreal Editor and a play-in-editor simulation.
  - [`examples/control_electric_dreams_sample`](../examples/control_electric_dreams_sample) demonstrates how to control Epic Games' `ElectricDreams` project.
  - [`examples/control_game_animation_sample`](../examples/control_game_animation_sample) demonstrates how to control Epic Games' `GameAnimationSample` project.
  - [`examples/control_metahumans_sample`](../examples/control_metahumans_sample) demonstrates how to control Epic Games' `MetaHumans` project.
  - [`examples/control_simple_agent`](../examples/control_simple_agent) demonstrates how to control a simple agent and obtain egocentric visual observations.
  - [`examples/control_stackobot_sample`](../examples/control_stackobot_sample) demonstrates how to control Epic Games' `StackOBot` project.
  - [`examples/enhanced_input`](../examples/enhanced_input) demonstrates how to interact with Unreal's Enhanced Input system.
  - [`examples/flashlight`](../examples/flashlight) demonstrates interactive and programmatic flashlight control, including a Rerun stream, orbit collection workflow for active-illumination inspection, and an Infinigen indoor FBX import setup script.
  - [`examples/get_class_info`](../examples/get_class_info) demonstrates how to interact with Unreal's runtime reflection system.
  - [`examples/getting_started`](../examples/getting_started) demonstrates how to spawn an object and access object properties.
  - [`examples/getting_started_editor`](../examples/getting_started_editor) demonstrates how to spawn an object using the Unreal Editor's built-in Python API.
  - [`examples/getting_started_notebook`](../examples/getting_started_notebook) demonstrates how to interoperate with Jupyter notebooks.
  - [`examples/import_humoto_dataset`](../examples/import_humoto_dataset) demonstrates how to import animation sequences from the Humoto dataset.
  - [`examples/import_mixamo_dataset`](../examples/import_mixamo_dataset) demonstrates how to import animation sequences from Mixamo.
  - [`examples/import_stanford_dataset`](../examples/import_stanford_dataset) demonstrates how to import custom objects from the Stanford 3D Scanning Repository.
  - [`examples/movie_render_queue`](../examples/movie_render_queue) demonstrates how to interact with Unreal's Movie Render Queue system.
  - [`examples/mujoco_interop`](../examples/mujoco_interop) demonstrates how to interoperate with the MuJoCo physics engine.
  - [`examples/numpy_interop`](../examples/numpy_interop) demonstrates how to efficiently pass NumPy arrays to and from Unreal entities.
  - [`examples/open_level`](../examples/open_level) demonstrates how to dynamically change levels.
  - [`examples/render_image`](../examples/render_image) demonstrates how to spawn a camera sensor object and render an image.
  - [`examples/render_image_async`](../examples/render_image_async) demonstrates how to render an image using the asynchronous API available in SPEAR.
  - [`examples/render_image_dataset`](../examples/render_image_dataset) demonstrates how to generate random camera poses and render a collection of images.
  - [`examples/render_image_hypersim`](../examples/render_image_hypersim) demonstrates how to render images that match the Hypersim dataset.
  - [`examples/render_image_editor`](../examples/render_image_editor) demonstrates how to render an image using the Unreal Editor's built-in Python API.
  - [`examples/render_image_multi_view`](../examples/render_image_multi_view) demonstrates how to render from a multi-view camera rig.
  - [`examples/sample_nav_mesh`](../examples/sample_nav_mesh) demonstrates how to sample points and shortest paths from Unreal's nav mesh system.

## Running the flashlight Rerun stream

The flashlight example includes a live programmatic stream that follows the
current viewport camera, controls an attached spotlight from Python, and logs
camera-aligned active-illumination observations to Rerun.

```console
python examples/flashlight/run_programmatic_rerun.py --map japanese_office_dark --movement-speed 600 --disable-scene-lights
```

The stream logs final-tone-curve RGB, metric depth, and a normalized depth RGB
preview as 2D image inspection streams at `rgb`, `depth_meters`, and
`depth_meters_visualization`, and it logs a matplotlib-rendered Unreal X/Y
game-world plot in meters at `camera_position_plot`. It does not create a shared
`images` parent, 3D Rerun view, camera frustum, projected RGB plane, point
cloud, 3D trajectory, or spatial `spear` hierarchy. Camera world position is
logged as non-spatial status scalars under `status/camera/`, and flashlight
intensity, enabled state, yaw offset, pitch offset, and text status are logged
under `status/light/`.
The script sends a fixed Rerun blueprint with separate views for each image
stream and status group, so the viewer should not use the default `/` combined
view.

Programmatic control lives in
`examples/flashlight/run_programmatic_rerun.py`: edit
`compute_light_command` to return a `LightCommand` for each frame. The hook
receives elapsed time, the frame index, the current viewport description, and
the previous light command, so it can toggle the flashlight, change intensity,
or adjust yaw and pitch offsets while the stream is running.

The script spawns Rerun by default. Pass `--no-rerun-spawn` to connect from an
already running Rerun viewer. Live SPEAR/Rerun validation requires a running
simulator and viewer; see [`examples/flashlight`](../examples/flashlight) for
the full workflow, including the imported Japanese office map and rendered
flythrough helpers.

The flashlight example can also launch a cooked map by Unreal content path. For
example, after following the Infinigen import and cook workflow in
[`Importing and Exporting Assets`](importing_and_exporting_assets.md), run:

```console
python examples/flashlight/run.py \
  --map-path /Game/SPEAR/Scenes/infinigen_indoors_0000/Maps/infinigen_indoors_0000 \
  --movement-speed 600
```

A larger validated imported scene is also available at
`/Game/SPEAR/Scenes/one_bed_apartment/Maps/one_bed_apartment`; it was cooked
successfully after importing with collision, material, and texture import
disabled. A separate free-space flythrough run has produced complete 1080p
MP4s for quick visual review, but the map still needs interactive inspection of
scale, lighting, collision, and player-start usability before data collection.

A compact validated imported college classroom scene is available at
`/Game/SPEAR/Scenes/college_classroom/Maps/college_classroom`; it was cooked
successfully after importing `285` static mesh assets with collision, material,
and texture import disabled. It still needs interactive visual/runtime
inspection before data collection.

## Running the realistic live cafeteria flashlight

For live cafeteria teleop with very dim scene lights and a profiled realistic
flashlight, run:

```console
python examples/flashlight/run.py \
  --map cafeteria_500sqft_v2 \
  --live-lighting-mode realistic \
  --flashlight-profile realistic_live_flashlight \
  --scene-light-intensity-scale 0.0005 \
  --movement-speed 600 \
  --disable-auto-exposure \
  --startup-warmup-seconds 3
```

This mode suppresses auto exposure and local exposure so dim fixture-light
changes remain visible, while preserving Lumen global illumination, Lumen
reflections, specular/material response, and related live rendering behavior.
In realistic live mode, `run.py` now requests hardware ray tracing by default
through launch-time renderer settings and matching runtime console commands.
Use `--disable-hardware-ray-tracing` only when intentionally testing the
non-hardware-RT path.

On Linux, the SpearSim project is configured to cook/package with Vulkan SM6
and ray tracing enabled by overriding `LinuxTargetSettings` in
`cpp/unreal_projects/SpearSim/Config/DefaultEngine.ini`: remove
`SF_VULKAN_SM5`, add `SF_VULKAN_SM6`, and set `bEnableRayTracing=True`. The
2026-07-08 clean cafeteria cook/package for `cafeteria_500sqft_v2` and
`cafeteria_500sqft_v2_flashlight_validation_dark` was approved at the package
artifact level as VULKAN_SM6 and not SM5-only. Evidence included VULKAN_SM6
shader autogen, SF_VULKAN_SM6 shader compile jobs, and
`Engine/GlobalShaderCache-VULKAN_SM6.bin` in both the archive pak listing and
the cooked filesystem artifact scan; the checked artifacts had no VULKAN_SM5,
`GlobalShaderCache-VULKAN_SM5`, or `SF_VULKAN_SM5` signatures.

The `realistic_live_flashlight` profile uses the checked-in beam/profile values
instead of ad hoc numeric tuning, including inverse-square flashlight falloff.
For brighter live trials, `realistic_live_flashlight_2x` preserves the same
realistic live settings while doubling flashlight intensity to `1600.0`.
During live teleop, the left gamepad trigger decreases flashlight intensity and
the right trigger increases it on the existing spotlight without restarting the
scene. Runtime intensity is clamped; override the defaults with
`--intensity-adjust-rate`, `--intensity-min`, and `--intensity-max` when a trial
needs a narrower or wider control range. The trigger axes default to
`Gamepad_LeftTriggerAxis` and `Gamepad_RightTriggerAxis`; use
`--intensity-down-key` and `--intensity-up-key` to remap them, and tune
`--intensity-trigger-deadzone` if the gamepad reports trigger noise near rest.

As of 2026-07-08, static/unit validation and package artifact validation have
passed, but live runtime validation of this exact command still has not run in
a display-capable session. The headless agent shell had empty `DISPLAY` and
`WAYLAND_DISPLAY`, so runtime validation was not attempted after the SM6 cook.
Re-run from an environment with a working Vulkan/NVIDIA display before treating
visual behavior or runtime hardware-RT enablement as validated. The expected
runtime log signatures are `Platform=VULKAN_SM6`, ray tracing enabled
dynamically, ray tracing shaders enabled, and hardware RT readback
`confirmed=true`.

## Running the flashlight orbit collection workflow

The flashlight example can save a user-selected orbit around a target point and
then render RGB and depth-visualization videos for multiple light settings. The
workflow helper runs the current cafeteria v2 natural flashlight profile by
default: fixed exposure, `--scene-light-intensity-scale 0.2`, and the
`real_handheld_16in_16in` profile from
`examples/flashlight/flashlight_profiles.json`. That profile models a 16 inch
diameter beam at 16 inches with visible direct/contact shadows and modest
indirect bounce. Existing numeric flags still override profile values. It also
disables scene-capture render history for orbit captures by relying on the
Python script default. Use teleop mode to navigate to the view you want, select
the target point with
`Gamepad_RightShoulder`, and preview the visible orbit with
`Gamepad_LeftShoulder`:

```console
examples/flashlight/run_orbit_workflow.sh teleop
```

Teleop mode writes an orbit spec JSON containing the map, start camera pose,
selected target point, orbit radius, duration, FPS, image size, field of view,
and baseline light settings. The preview restores the spectator pawn pose and
control rotation after the orbit. If target selection does not hit geometry, the
script records a fallback target along the camera forward direction.

The helper defaults to the cafeteria v2 map path,
`examples/flashlight/orbit_spec.json`,
`examples/flashlight/orbit_light_settings.json`, and
`examples/flashlight/orbit_collection_output`. Override these defaults with
matching helper flags, or with environment variables such as
`SPEAR_ORBIT_MAP_PATH`, `SPEAR_ORBIT_SPEC_FILE`,
`SPEAR_ORBIT_LIGHT_SETTINGS_FILE`, `SPEAR_ORBIT_OUTPUT_DIR`,
`SPEAR_SCENE_LIGHT_INTENSITY_SCALE`, `SPEAR_FLASHLIGHT_PROFILE`, and
`SPEAR_FLASHLIGHT_SOURCE_RADIUS`.

Render mode reuses the saved orbit spec. By default, the
`color-flashlight-only` preset writes temporary settings and produces the four
active-illumination RGB outputs `scene_on_flashlight_off`,
`scene_on_flashlight_on`, `scene_off_flashlight_off`, and
`scene_off_flashlight_on`:

```console
examples/flashlight/run_orbit_workflow.sh render
```

`--scene-light-intensity-scale` controls scene lights for scene-on renders. The
default scene-off pass keeps material-color RGB capture active and forces scene
light scale `0.0`, independent of the configured scene-on scale. Use
`--render-preset validation` to render the checked-in
`examples/flashlight/orbit_light_settings.json` diagnostic settings, including
scene-off lighting-only capture entries. Default render mode uses natural
lighting so teleop and render share the same profile; validation mode switches
to the `soft_flood_validation` profile and `--render-lighting-mode validation`
to preserve the older GI/reflection-disabled diagnostic path. The helper keeps
fixed exposure explicit with `--disable-auto-exposure` and does not require
users to hand-write JSON. `scene_off_flashlight_off` is a no-flashlight-ever
diagnostic control for
baked, static, or environment illumination that can remain after runtime scene
lights are disabled; the validation JSON setting uses `"spawn_flashlight":
false` so the scene-off setup does not warm up with the saved orbit baseline
flashlight. Validation scene-off passes hide existing scene light components,
zero direct and indirect lighting intensity, and also try to disable available
environment contributors such as sky, fog, reflection capture, and post-process
components before any flashlight setting that needs a spawned spotlight. Render
history is disabled by default in `run_orbit_collection.py`,
so each explicit capture is treated as a camera cut and the script attempts
capture-component render-state readback after initialization. The metadata
reports whether that readback verified render-history disablement for every
capture component. Lumen GI/reflections, screen-space reflections, Temporal AA,
and motion blur are also disabled for deterministic data collection. Before
writing output frames, render mode runs readback-only warm-up captures after
camera sensor setup and after each light-setting change; those warm-up captures
are discarded so `frame_0000` is the first saved orbit frame for that setting. Use
`examples/flashlight/run_orbit_workflow.sh render -- --enable-render-history`
only when deliberately comparing against normal temporal rendering.

For flashlight-only validation where the scene-off baseline must be black, use
the dark cafeteria validation map:
`/Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2_flashlight_validation_dark`.
A 2026-07-01 validation run against that map wrote
`examples/flashlight/orbit_collection_output_validation_dark_map`; all four
default light settings produced complete RGB/depth videos and 240-frame RGB and
depth frame sets. In that run, `scene_off_flashlight_off` stayed black for all
frames with median mean luma `0.0`, `scene_off_flashlight_on` showed localized
flashlight-only illumination with median mean luma about `19.64`, both
scene-on settings remained lit, and saved RGB/depth frames showed no progressive
exposure accumulation. The same run still reported unverified capture
render-history/show-flag readback in metadata, so treat the saved-frame luma
checks as the acceptance evidence and keep those metadata fields visible when
validating future maps.

The orbit collection script keeps its config compatible with both current
`SP_CORE` INI override keys and older standalone `SpearSim` binaries that still
query legacy `*_INI_CONFIG_VALUES` maps. Users should keep `user_config.yaml`
focused on local overrides such as `SPEAR.INSTANCE.GAME_EXECUTABLE`; the script
fills the missing legacy maps at runtime when needed.

Each light setting writes RGB PNG frames under
`orbit_collection_output/<name>/frames/rgb/`, raw metric depth `.npy` frames
under `orbit_collection_output/<name>/frames/depth_meters_npy/`, and viridis
depth PNG frames under
`orbit_collection_output/<name>/frames/depth_meters_viridis/`. It also writes
`rgb.mp4` and `depth_meters_viridis.mp4`. The `.npy` frames preserve raw metric
depth, while the viridis PNG and video outputs use one stable depth range per
light setting. Each setting directory also includes `metadata.json` with the
scene-light state and deterministic capture settings used for that render.

With the default helper settings, the MP4 files are:

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

By default, that visualization range clips to the 1st and 99th percentiles of
finite metric depth samples so far-plane outliers do not wash out the orbit
contrast. Use `--depth-visualization-lower-percentile` and
`--depth-visualization-upper-percentile` to tune clipping, or
`--depth-visualization-min-meters` and `--depth-visualization-max-meters` for
fixed visualization bounds. For large renders,
`--depth-visualization-max-samples` caps the number of finite depth samples used
to estimate percentile bounds; it defaults to `1000000`. The default orbit spec
and output paths are generated artifacts and are ignored by Git. Live render
validation still requires a running SPEAR simulator.
