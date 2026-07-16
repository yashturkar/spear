import argparse
import math
from pathlib import Path

import bpy


parser = argparse.ArgumentParser()
parser.add_argument("--output-folder", required=True)
args = parser.parse_args()

OUT_DIR = Path(args.output_folder)
BLEND_PATH = OUT_DIR / "scene.blend"


def reset_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def material(name, color, roughness=0.62, metallic=0.0, alpha=1.0, emission=None, emission_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Alpha"].default_value = alpha
    if emission is not None and "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = emission
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    if alpha < 1.0:
        mat.blend_method = "BLEND"
        mat.use_screen_refraction = True
    return mat


MATS = {}


def init_materials():
    MATS.update(
        {
            "wall": material("warm_white_scrubbable_kitchen_wall", (0.78, 0.77, 0.72, 1), roughness=0.75),
            "tile": material("matte_quarry_tile_floor", (0.46, 0.39, 0.33, 1), roughness=0.72),
            "grout": material("dark_sanitary_grout", (0.16, 0.15, 0.14, 1), roughness=0.78),
            "ceiling": material("off_white_washable_ceiling", (0.81, 0.80, 0.76, 1), roughness=0.82),
            "stainless": material("brushed_stainless_steel_kitchen_equipment", (0.58, 0.58, 0.56, 1), roughness=0.31, metallic=0.75),
            "dark_metal": material("dark_cast_iron_cooking_surface", (0.03, 0.032, 0.03, 1), roughness=0.48, metallic=0.45),
            "rubber": material("black_anti_fatigue_rubber_mat", (0.025, 0.025, 0.023, 1), roughness=0.8),
            "wood": material("sealed_maple_cutting_board", (0.63, 0.47, 0.29, 1), roughness=0.5),
            "plastic": material("muted_blue_food_safe_plastic", (0.13, 0.22, 0.32, 1), roughness=0.64),
            "green": material("muted_green_crate_plastic", (0.18, 0.31, 0.22, 1), roughness=0.65),
            "red": material("muted_red_control_knob", (0.46, 0.08, 0.06, 1), roughness=0.45),
            "paper": material("off_white_prep_label_paper", (0.86, 0.84, 0.77, 1), roughness=0.76),
            "glass": material("slightly_green_safety_glass", (0.58, 0.72, 0.74, 0.32), roughness=0.08, alpha=0.32),
            "fixture": material("warm_diffused_linear_light_lens", (1.0, 0.88, 0.62, 1), roughness=0.28, emission=(1.0, 0.80, 0.50, 1), emission_strength=0.22),
            "outside": material("dim_exterior_service_alley", (0.25, 0.26, 0.25, 1), roughness=0.74),
        }
    )


def assign(obj, mat):
    obj.data.materials.append(mat)
    return obj


def link_to_collection(obj, collection_name):
    coll = bpy.data.collections.get(collection_name)
    if coll is None:
        coll = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(coll)
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    coll.objects.link(obj)


def cube(name, loc, scale, mat_key=None, collection="kitchen"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat_key:
        assign(obj, MATS[mat_key])
    link_to_collection(obj, collection)
    return obj


def cyl(name, loc, radius, depth, mat_key=None, vertices=24, rotation=(0, 0, 0), collection="kitchen"):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    if mat_key:
        assign(obj, MATS[mat_key])
    link_to_collection(obj, collection)
    return obj


def bevel(obj, amount=0.025, segments=2):
    mod = obj.modifiers.new(name="small_softened_real_edge", type="BEVEL")
    mod.width = amount
    mod.segments = segments
    mod.affect = "EDGES"
    obj.modifiers.new(name="weighted_normals", type="WEIGHTED_NORMAL")
    return obj


def appliance_block(name, loc, scale, collection="equipment"):
    body = bevel(cube(f"{name}_stainless_body", loc, scale, "stainless", collection), 0.025)
    return body


def add_room_shell():
    width = 9.6
    depth = 9.6
    height = 3.2
    bevel(cube("floor_quarry_tile_slab_approx_1000_sqft", (0, 0, -0.04), (width, depth, 0.08), "tile", "room_shell"), 0.01)
    for x in [v * 0.8 for v in range(-5, 6)]:
        cube(f"floor_grout_line_x_{x:.1f}", (x, 0, 0.01), (0.018, depth - 0.15, 0.012), "grout", "room_shell")
    for y in [v * 0.8 for v in range(-5, 6)]:
        cube(f"floor_grout_line_y_{y:.1f}", (0, y, 0.012), (width - 0.15, 0.018, 0.012), "grout", "room_shell")

    bevel(cube("ceiling_washable_panel_plane", (0, 0, height), (width, depth, 0.08), "ceiling", "room_shell"), 0.01)
    bevel(cube("north_prep_wall_with_service_door", (0, -4.85, height / 2), (width, 0.10, height), "wall", "room_shell"), 0.01)
    bevel(cube("south_storage_wall", (0, 4.85, height / 2), (width, 0.10, height), "wall", "room_shell"), 0.01)
    bevel(cube("west_cookline_wall", (-4.85, 0, height / 2), (0.10, depth, height), "wall", "room_shell"), 0.01)
    bevel(cube("east_wall_below_real_windows", (4.85, 0, 0.55), (0.10, depth, 1.10), "wall", "room_shell"), 0.01)
    bevel(cube("east_wall_above_real_windows", (4.85, 0, 2.75), (0.10, depth, 0.90), "wall", "room_shell"), 0.01)
    for idx, y in enumerate([-3.65, -1.75, 0.0, 1.75, 3.65]):
        bevel(cube(f"east_window_mullion_or_end_{idx}", (4.85, y, 1.68), (0.10, 0.18 if idx not in [0, 4] else 0.62, 1.35), "wall", "room_shell"), 0.01)
    for idx, y in enumerate([-2.65, -0.85, 0.85, 2.65]):
        cube(f"real_high_kitchen_window_glass_{idx}", (4.92, y, 1.68), (0.035, 1.22, 1.22), "glass", "room_shell")
        cube(f"window_stainless_frame_top_{idx}", (4.89, y, 2.31), (0.12, 1.34, 0.06), "stainless", "room_shell")
        cube(f"window_stainless_frame_bottom_{idx}", (4.89, y, 1.05), (0.12, 1.34, 0.06), "stainless", "room_shell")

    bevel(cube("service_alley_slab_visible_through_windows", (6.0, 0, -0.03), (2.1, 8.9, 0.05), "outside", "exterior_context"), 0.01)
    bevel(cube("distant_service_alley_wall", (6.95, 0, 1.45), (0.10, 8.9, 2.9), "outside", "exterior_context"), 0.01)
    bevel(cube("rear_receiving_door_metal_panel", (-2.9, 4.91, 1.05), (1.05, 0.06, 2.10), "stainless", "room_shell"), 0.02)
    cyl("receiving_door_pull_bar", (-2.38, 4.97, 1.05), 0.032, 0.72, "dark_metal", vertices=12, rotation=(0, math.pi / 2, 0), collection="room_shell")


def add_table(name, loc, scale=(1.7, 0.75, 0.08)):
    x, y, z = loc
    bevel(cube(f"{name}_stainless_top", (x, y, z), scale, "stainless", "prep_tables"), 0.025)
    for dx in [-scale[0] / 2 + 0.08, scale[0] / 2 - 0.08]:
        for dy in [-scale[1] / 2 + 0.08, scale[1] / 2 - 0.08]:
            cyl(f"{name}_round_leg_{dx:.1f}_{dy:.1f}", (x + dx, y + dy, z / 2), 0.035, z, "stainless", vertices=12, collection="prep_tables")
    cube(f"{name}_undershelf", (x, y, 0.42), (scale[0] - 0.12, scale[1] - 0.12, 0.045), "stainless", "prep_tables")


def add_cookline():
    y_positions = [-3.25, -2.05, -0.85, 0.35, 1.55]
    names = ["six_burner_range", "flat_top_griddle", "twin_fryer_bank", "convection_oven", "steam_table"]
    for name, y in zip(names, y_positions):
        appliance_block(name, (-4.22, y, 0.58), (0.88, 0.95, 1.05))
        cube(f"{name}_black_cooking_surface", (-4.20, y, 1.14), (0.78, 0.78, 0.07), "dark_metal", "equipment")
        for i, knob_y in enumerate([-0.28, 0.0, 0.28]):
            cyl(f"{name}_red_control_knob_{i}", (-3.74, y + knob_y, 0.82), 0.045, 0.035, "red", vertices=16, rotation=(0, math.pi / 2, 0), collection="equipment")
    cube("continuous_stainless_exhaust_hood", (-4.26, -0.85, 2.28), (1.05, 6.1, 0.42), "stainless", "equipment")
    for y in [-3.35, -2.0, -0.65, 0.7, 1.95]:
        cube(f"hood_grease_filter_panel_{y}", (-3.72, y, 2.18), (0.055, 0.86, 0.26), "dark_metal", "equipment")
    cube("cookline_black_anti_fatigue_mat", (-3.52, -0.85, 0.025), (0.9, 6.4, 0.035), "rubber", "equipment")


def add_sinks_and_dish_area():
    appliance_block("three_compartment_sink", (1.65, 4.25, 0.72), (2.4, 0.72, 0.85), "plumbing")
    for x in [0.95, 1.65, 2.35]:
        cube(f"sink_basin_dark_insert_{x}", (x, 3.88, 1.02), (0.58, 0.38, 0.08), "dark_metal", "plumbing")
        cyl(f"gooseneck_faucet_{x}", (x, 3.72, 1.30), 0.025, 0.38, "stainless", vertices=12, rotation=(math.pi / 2, 0, 0), collection="plumbing")
    appliance_block("commercial_dishwasher", (3.45, 4.18, 0.74), (0.95, 0.80, 1.05), "plumbing")
    cube("dishwasher_pull_handle", (3.45, 3.74, 1.05), (0.62, 0.035, 0.055), "dark_metal", "plumbing")
    cube("dish_area_floor_mat", (2.55, 3.50, 0.025), (2.7, 0.9, 0.035), "rubber", "plumbing")


def add_storage_and_cold_side():
    appliance_block("walk_in_cooler_box", (-2.25, 4.15, 1.25), (2.35, 1.25, 2.5), "storage")
    cube("walk_in_cooler_door", (-1.70, 3.48, 1.12), (0.78, 0.06, 1.9), "stainless", "storage")
    cyl("walk_in_cooler_vertical_handle", (-1.28, 3.43, 1.12), 0.03, 0.55, "dark_metal", vertices=12, collection="storage")
    for rack_idx, x in enumerate([-3.75, -2.55, -1.35, 3.25]):
        cube(f"wire_shelving_back_post_{rack_idx}_left", (x - 0.48, 2.30, 0.92), (0.045, 0.045, 1.65), "stainless", "storage")
        cube(f"wire_shelving_back_post_{rack_idx}_right", (x + 0.48, 2.30, 0.92), (0.045, 0.045, 1.65), "stainless", "storage")
        for level, z in enumerate([0.32, 0.72, 1.12, 1.52]):
            cube(f"wire_shelf_{rack_idx}_{level}", (x, 2.30, z), (1.05, 0.50, 0.035), "stainless", "storage")
            for item in range(3):
                mat = "green" if (item + rack_idx + level) % 2 else "plastic"
                cube(f"food_storage_bin_{rack_idx}_{level}_{item}", (x - 0.32 + item * 0.32, 2.26, z + 0.12), (0.24, 0.34, 0.18), mat, "storage")


def add_prep_island_and_pass():
    add_table("central_prep_island_left", (-0.95, -0.65, 0.93), (1.9, 0.82, 0.08))
    add_table("central_prep_island_right", (1.05, -0.65, 0.93), (1.9, 0.82, 0.08))
    for x in [-1.45, -0.65, 0.55, 1.38]:
        cube(f"maple_cutting_board_{x}", (x, -0.65, 1.00), (0.52, 0.36, 0.045), "wood", "prep_tables")
    for x in [-1.85, 1.85]:
        appliance_block(f"undercounter_refrigerated_drawer_{x}", (x, -0.65, 0.46), (0.58, 0.72, 0.52), "prep_tables")
    cube("open_service_pass_counter", (0.95, -4.25, 1.02), (2.5, 0.72, 0.95), "stainless", "service_pass")
    cube("service_pass_heat_lamp_lens", (0.95, -4.55, 1.82), (2.35, 0.08, 0.08), "fixture", "service_pass")
    for x in [-0.05, 0.65, 1.35, 2.05]:
        cube(f"plated_food_placeholder_{x}", (x, -4.20, 1.52), (0.44, 0.28, 0.06), "paper", "service_pass")


def add_small_details():
    for idx, (x, y) in enumerate([(-2.2, -0.8), (-1.0, -0.38), (0.7, -0.95), (1.5, -0.35), (2.9, 0.95)]):
        cyl(f"stainless_stock_pot_{idx}", (x, y, 1.13), 0.16, 0.26, "stainless", vertices=24, collection="details")
        cyl(f"stock_pot_dark_opening_{idx}", (x, y, 1.27), 0.13, 0.02, "dark_metal", vertices=24, collection="details")
    for idx, y in enumerate([-1.9, -0.7, 0.5, 1.7]):
        cube(f"wall_clipboard_order_ticket_{idx}", (-4.91, y, 1.55), (0.035, 0.34, 0.24), "paper", "details")
    for idx, x in enumerate([-3.5, -2.5, 2.4, 3.35]):
        cube(f"rolling_speed_rack_frame_{idx}", (x, 0.95, 0.85), (0.52, 0.42, 1.40), "stainless", "details")
        for z in [0.32, 0.62, 0.92, 1.22]:
            cube(f"sheet_pan_{idx}_{z}", (x, 0.95, z), (0.48, 0.38, 0.025), "dark_metal", "details")
    for i, x in enumerate([-3.1, -1.1, 1.1, 3.1]):
        cube(f"ceiling_linear_fixture_lens_{i}", (x, -0.55, 3.00), (1.45, 0.18, 0.045), "fixture", "lighting_reference")
        cube(f"ceiling_linear_fixture_housing_{i}", (x, -0.55, 3.04), (1.58, 0.25, 0.06), "stainless", "lighting_reference")
    for i, y in enumerate([-3.4, 3.4]):
        cube(f"secondary_dim_fixture_lens_{i}", (0, y, 3.00), (1.2, 0.16, 0.045), "fixture", "lighting_reference")


def add_camera_and_light():
    bpy.ops.object.light_add(type="AREA", location=(0, -0.5, 2.9))
    light = bpy.context.object
    light.name = "dim_blender_preview_area_light_not_imported_as_fixture"
    light.data.energy = 80
    light.data.size = 5.0
    bpy.ops.object.camera_add(location=(4.2, -5.4, 2.2), rotation=(math.radians(66), 0, math.radians(40)))
    bpy.context.scene.camera = bpy.context.object


def main():
    reset_scene()
    init_materials()
    add_room_shell()
    add_cookline()
    add_sinks_and_dish_area()
    add_storage_and_cold_side()
    add_prep_island_and_pass()
    add_small_details()
    add_camera_and_light()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    print(f"WROTE_BLEND:{BLEND_PATH}")
    print("SCENE_INTENT:restaurant_kitchen_1000sqft commercial kitchen with cookline prep sinks storage service circulation and dim fixture references")
    print("APPROX_FLOOR_AREA_SQFT:992")


if __name__ == "__main__":
    main()
