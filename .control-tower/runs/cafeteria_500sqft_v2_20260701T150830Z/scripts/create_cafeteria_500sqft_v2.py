import math
from pathlib import Path

import bpy


OUT_DIR = Path("/home/yashturkar/Workspace/infinigen/outputs/cafeteria_500sqft_v2/coarse")
BLEND_PATH = OUT_DIR / "scene.blend"


def reset_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def material(name, color, roughness=0.6, metallic=0.0, alpha=1.0, emission=None, emission_strength=0.0):
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
            "wall": material("soft_white_painted_drywall", (0.76, 0.74, 0.68, 1), roughness=0.76),
            "service_wall": material("matte_warm_gray_service_wall", (0.36, 0.35, 0.32, 1), roughness=0.72),
            "floor": material("matte_large_format_gray_tile", (0.42, 0.41, 0.38, 1), roughness=0.68),
            "floor_line": material("subtle_dark_grout_lines", (0.20, 0.20, 0.19, 1), roughness=0.75),
            "ceiling": material("off_white_acoustic_ceiling", (0.80, 0.79, 0.74, 1), roughness=0.82),
            "wood": material("sealed_natural_oak_tabletop", (0.52, 0.39, 0.25, 1), roughness=0.44),
            "wood_dark": material("dark_stained_counter_front", (0.23, 0.18, 0.13, 1), roughness=0.55),
            "metal": material("satin_brushed_stainless_steel", (0.56, 0.56, 0.54, 1), roughness=0.34, metallic=0.65),
            "black": material("soft_black_plastic", (0.02, 0.02, 0.02, 1), roughness=0.64),
            "chair_a": material("desaturated_sage_polypropylene_chair", (0.33, 0.39, 0.32, 1), roughness=0.56),
            "chair_b": material("muted_terracotta_polypropylene_chair", (0.46, 0.29, 0.22, 1), roughness=0.56),
            "chair_c": material("charcoal_polypropylene_chair", (0.15, 0.15, 0.14, 1), roughness=0.58),
            "counter_top": material("matte_light_solid_surface_countertop", (0.70, 0.67, 0.60, 1), roughness=0.36),
            "menu": material("dark_gray_menu_board", (0.03, 0.035, 0.032, 1), roughness=0.85),
            "paper": material("off_white_paper", (0.86, 0.83, 0.75, 1), roughness=0.78),
            "tray": material("gray_green_serving_tray", (0.25, 0.32, 0.25, 1), roughness=0.58),
            "cup": material("warm_white_paper_cup", (0.88, 0.86, 0.79, 1), roughness=0.64),
            "coffee": material("dark_coffee_liquid", (0.07, 0.035, 0.018, 1), roughness=0.28),
            "fruit_red": material("muted_apple_red", (0.48, 0.10, 0.08, 1), roughness=0.46),
            "fruit_orange": material("muted_orange_peel", (0.62, 0.30, 0.11, 1), roughness=0.5),
            "bread": material("wheat_bread", (0.64, 0.50, 0.33, 1), roughness=0.7),
            "glass": material("clear_slightly_green_window_glass", (0.55, 0.72, 0.75, 0.30), roughness=0.06, alpha=0.30),
            "drink_red": material("muted_red_soda_can", (0.44, 0.08, 0.07, 1), roughness=0.36, metallic=0.25),
            "drink_blue": material("muted_blue_soda_can", (0.10, 0.20, 0.36, 1), roughness=0.36, metallic=0.25),
            "led": material("warm_diffused_led_lens", (1.0, 0.92, 0.76, 1), roughness=0.22, emission=(1.0, 0.86, 0.58, 1), emission_strength=0.35),
            "outside_ground": material("exterior_concrete_walk_and_planter", (0.34, 0.35, 0.33, 1), roughness=0.72),
            "outside_wall": material("distant_brick_building_seen_through_windows", (0.38, 0.30, 0.25, 1), roughness=0.78),
            "outside_green": material("muted_exterior_planting", (0.20, 0.31, 0.19, 1), roughness=0.8),
            "sky": material("pale_daylight_sky_backdrop", (0.58, 0.66, 0.72, 1), roughness=0.5),
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


def cube(name, loc, scale, mat=None, collection=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat is not None:
        assign(obj, mat)
    if collection is not None:
        link_to_collection(obj, collection)
    return obj


def cyl(name, loc, radius, depth, mat=None, vertices=24, rotation=(0, 0, 0), collection=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    if mat is not None:
        assign(obj, mat)
    if collection is not None:
        link_to_collection(obj, collection)
    return obj


def sphere(name, loc, radius, mat=None, collection=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius, location=loc)
    obj = bpy.context.object
    obj.name = name
    if mat is not None:
        assign(obj, mat)
    if collection is not None:
        link_to_collection(obj, collection)
    return obj


def add_bevel(obj, amount=0.02, segments=2):
    bevel = obj.modifiers.new(name="small_realistic_edge_bevel", type="BEVEL")
    bevel.width = amount
    bevel.segments = segments
    bevel.affect = "EDGES"
    obj.modifiers.new(name="weighted_normals", type="WEIGHTED_NORMAL")
    return obj


def add_room_shell():
    add_bevel(cube("floor_large_format_tile_slab", (0, 0, -0.04), (7.45, 6.65, 0.08), MATS["floor"], "room_shell"), 0.01)
    for y in [-2.4, -1.2, 0.0, 1.2, 2.4]:
        cube(f"floor_grout_line_y_{y}", (0, y, 0.007), (7.35, 0.018, 0.012), MATS["floor_line"], "room_shell")
    for x in [-2.4, -1.2, 0.0, 1.2, 2.4]:
        cube(f"floor_grout_line_x_{x}", (x, 0, 0.008), (0.018, 6.55, 0.012), MATS["floor_line"], "room_shell")

    add_bevel(cube("ceiling_acoustic_panel_plane", (0, 0, 3.05), (7.45, 6.65, 0.08), MATS["ceiling"], "room_shell"), 0.01)
    add_bevel(cube("front_service_wall_warm_gray", (0, -3.25, 1.5), (7.45, 0.10, 3.0), MATS["service_wall"], "room_shell"), 0.01)
    add_bevel(cube("back_entry_wall_with_glass_door", (0, 3.25, 1.5), (7.45, 0.10, 3.0), MATS["wall"], "room_shell"), 0.01)
    add_bevel(cube("left_painted_wall", (-3.65, 0, 1.5), (0.10, 6.65, 3.0), MATS["wall"], "room_shell"), 0.01)

    add_bevel(cube("right_wall_below_real_window_openings", (3.65, 0, 0.47), (0.10, 6.65, 0.94), MATS["wall"], "room_shell"), 0.01)
    add_bevel(cube("right_wall_above_real_window_openings", (3.65, 0, 2.69), (0.10, 6.65, 0.62), MATS["wall"], "room_shell"), 0.01)
    for name, y, h in [
        ("right_window_wall_solid_end_negative_y", -2.85, 0.95),
        ("right_window_wall_mullion_0", -1.20, 0.16),
        ("right_window_wall_mullion_1", 0.00, 0.16),
        ("right_window_wall_mullion_2", 1.20, 0.16),
        ("right_window_wall_solid_end_positive_y", 2.85, 0.95),
    ]:
        add_bevel(cube(name, (3.65, y, 1.65), (0.10, h, 1.45), MATS["wall"], "room_shell"), 0.01)

    add_bevel(cube("rear_glass_entry_door", (-2.55, 3.31, 1.05), (0.95, 0.06, 2.10), MATS["glass"], "room_shell"), 0.02)
    cyl("entry_door_pull_handle", (-2.08, 3.36, 1.05), 0.035, 0.75, MATS["metal"], vertices=12, rotation=(0, math.pi / 2, 0), collection="room_shell")

    for idx, y in enumerate([-1.8, -0.6, 0.6, 1.8]):
        cube(f"right_real_window_glass_{idx}", (3.73, y, 1.65), (0.035, 0.98, 1.27), MATS["glass"], "room_shell")
        cube(f"right_real_window_frame_{idx}_top", (3.69, y, 2.31), (0.12, 1.08, 0.065), MATS["metal"], "room_shell")
        cube(f"right_real_window_frame_{idx}_bottom", (3.69, y, 0.99), (0.12, 1.08, 0.065), MATS["metal"], "room_shell")
        cube(f"right_real_window_frame_{idx}_left", (3.69, y - 0.52, 1.65), (0.12, 0.06, 1.33), MATS["metal"], "room_shell")
        cube(f"right_real_window_frame_{idx}_right", (3.69, y + 0.52, 1.65), (0.12, 0.06, 1.33), MATS["metal"], "room_shell")

    cube("exterior_concrete_walk_visible_through_windows", (4.85, 0.0, -0.02), (2.4, 6.4, 0.04), MATS["outside_ground"], "exterior_daylight_context")
    cube("distant_exterior_brick_wall_visible_through_windows", (5.95, 0.0, 1.35), (0.10, 6.6, 2.7), MATS["outside_wall"], "exterior_daylight_context")
    cube("pale_sky_strip_above_exterior_wall", (6.00, 0.0, 3.05), (0.08, 6.6, 1.00), MATS["sky"], "exterior_daylight_context")
    for idx, y in enumerate([-2.1, 0.1, 2.0]):
        cyl(f"exterior_planter_box_{idx}", (4.35, y, 0.25), 0.18, 0.70, MATS["outside_ground"], vertices=18, rotation=(math.pi / 2, 0, 0), collection="exterior_daylight_context")
        sphere(f"exterior_muted_shrub_{idx}", (4.35, y, 0.62), 0.32, MATS["outside_green"], "exterior_daylight_context")


def add_service_counter():
    add_bevel(cube("long_dark_stained_service_counter_front", (-1.35, -2.75, 0.62), (4.20, 0.62, 1.05), MATS["wood_dark"], "service_counter"), 0.03)
    add_bevel(cube("long_matte_light_countertop", (-1.35, -2.75, 1.18), (4.36, 0.82, 0.11), MATS["counter_top"], "service_counter"), 0.025)
    cube("stainless_sneeze_guard_glass", (-1.35, -2.35, 1.62), (4.05, 0.04, 0.72), MATS["glass"], "service_counter")
    for x in [-3.15, -2.0, -0.85, 0.30]:
        cube(f"counter_gray_green_tray_stack_{x}", (x, -2.42, 1.28), (0.55, 0.36, 0.055), MATS["tray"], "service_counter")

    add_bevel(cube("menu_board_left", (-2.25, -3.31, 2.12), (1.55, 0.05, 0.82), MATS["menu"], "service_counter"), 0.012)
    add_bevel(cube("menu_board_right", (-0.45, -3.31, 2.12), (1.55, 0.05, 0.82), MATS["menu"], "service_counter"), 0.012)
    for i, (x, z) in enumerate([(-2.25, 2.32), (-2.25, 2.09), (-2.25, 1.86), (-0.45, 2.32), (-0.45, 2.09), (-0.45, 1.86)]):
        cube(f"menu_chalk_line_{i}", (x, -3.35, z), (1.10, 0.018, 0.035), MATS["paper"], "service_counter")

    add_bevel(cube("drink_refrigerator_body", (2.45, -2.75, 1.02), (0.92, 0.62, 1.92), MATS["metal"], "service_counter"), 0.025)
    cube("drink_refrigerator_glass_door", (2.45, -2.39, 1.05), (0.74, 0.04, 1.52), MATS["glass"], "service_counter")
    for row, z in enumerate([0.55, 0.90, 1.25, 1.60]):
        cube(f"fridge_wire_shelf_{row}", (2.45, -2.43, z), (0.72, 0.08, 0.025), MATS["metal"], "service_counter")
        for col, x in enumerate([2.22, 2.45, 2.68]):
            cyl(f"fridge_can_r{row}_c{col}", (x, -2.48, z + 0.11), 0.055, 0.20, MATS["drink_red"] if (row + col) % 2 == 0 else MATS["drink_blue"], vertices=16, collection="service_counter")

    add_bevel(cube("coffee_station_base", (3.10, -0.95, 0.54), (0.72, 0.58, 0.92), MATS["wood_dark"], "service_counter"), 0.025)
    add_bevel(cube("coffee_machine_black_body", (3.10, -0.98, 1.14), (0.52, 0.40, 0.50), MATS["black"], "service_counter"), 0.025)
    cube("coffee_machine_metal_face", (3.10, -1.20, 1.18), (0.40, 0.035, 0.30), MATS["metal"], "service_counter")
    cyl("coffee_pot_glass", (3.08, -1.23, 0.86), 0.13, 0.16, MATS["coffee"], vertices=20, collection="service_counter")
    for i, x in enumerate([2.78, 2.92, 3.34, 3.48]):
        cyl(f"stacked_paper_cup_{i}", (x, -1.24, 0.94), 0.055, 0.16, MATS["cup"], vertices=16, collection="service_counter")


def add_chair(name, x, y, yaw, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, 0.46), rotation=(0, 0, yaw))
    seat = bpy.context.object
    seat.name = f"{name}_seat"
    seat.dimensions = (0.50, 0.46, 0.08)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign(seat, mat)
    link_to_collection(seat, "dining_tables")
    add_bevel(seat, 0.025)

    back_dx = -math.sin(yaw) * 0.24
    back_dy = -math.cos(yaw) * 0.24
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x + back_dx, y + back_dy, 0.82), rotation=(0, 0, yaw))
    back = bpy.context.object
    back.name = f"{name}_back"
    back.dimensions = (0.52, 0.07, 0.62)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign(back, mat)
    link_to_collection(back, "dining_tables")
    add_bevel(back, 0.025)

    for dx in [-0.19, 0.19]:
        for dy in [-0.17, 0.17]:
            lx = x + math.cos(yaw) * dx - math.sin(yaw) * dy
            ly = y + math.sin(yaw) * dx + math.cos(yaw) * dy
            cyl(f"{name}_leg_{dx}_{dy}", (lx, ly, 0.24), 0.022, 0.44, MATS["metal"], vertices=10, collection="dining_tables")


def add_table(name, x, y, chair_mat_a, chair_mat_b):
    add_bevel(cube(f"{name}_square_tabletop", (x, y, 0.74), (1.08, 1.08, 0.08), MATS["wood"], "dining_tables"), 0.035)
    cyl(f"{name}_central_pedestal", (x, y, 0.38), 0.07, 0.70, MATS["metal"], vertices=18, collection="dining_tables")
    cyl(f"{name}_round_table_base", (x, y, 0.06), 0.32, 0.05, MATS["metal"], vertices=28, collection="dining_tables")
    for index, (dx, dy, yaw, mat) in enumerate([(0, -0.78, 0, chair_mat_a), (0, 0.78, math.pi, chair_mat_b), (-0.78, 0, math.pi / 2, chair_mat_b), (0.78, 0, -math.pi / 2, chair_mat_a)]):
        add_chair(f"{name}_chair_{index}", x + dx, y + dy, yaw, mat)

    cube(f"{name}_gray_green_tray", (x - 0.20, y + 0.10, 0.815), (0.46, 0.32, 0.035), MATS["tray"], "dining_tables")
    cyl(f"{name}_paper_cup", (x + 0.24, y - 0.18, 0.89), 0.06, 0.16, MATS["cup"], vertices=16, collection="dining_tables")
    if name.endswith("0") or name.endswith("3"):
        cube(f"{name}_sandwich_plate", (x - 0.10, y + 0.05, 0.86), (0.32, 0.22, 0.025), MATS["paper"], "dining_tables")
        cube(f"{name}_sandwich_half_a", (x - 0.16, y + 0.05, 0.91), (0.14, 0.18, 0.055), MATS["bread"], "dining_tables")
        cube(f"{name}_sandwich_half_b", (x + 0.02, y + 0.05, 0.91), (0.14, 0.18, 0.055), MATS["bread"], "dining_tables")


def add_dining_area():
    table_specs = [
        ("table_0", -2.35, 0.15, MATS["chair_a"], MATS["chair_c"]),
        ("table_1", -0.75, 1.65, MATS["chair_b"], MATS["chair_c"]),
        ("table_2", 1.15, 0.05, MATS["chair_a"], MATS["chair_b"]),
        ("table_3", 2.20, 1.78, MATS["chair_c"], MATS["chair_a"]),
    ]
    for spec in table_specs:
        add_table(*spec)


def add_details():
    add_bevel(cube("low_condiment_station", (-3.05, 2.35, 0.62), (0.92, 0.48, 0.94), MATS["wood_dark"], "details"), 0.025)
    cube("condiment_station_countertop", (-3.05, 2.35, 1.12), (1.02, 0.58, 0.08), MATS["counter_top"], "details")
    for i, (x, mat) in enumerate([(-3.32, MATS["fruit_red"]), (-3.12, MATS["fruit_orange"]), (-2.92, MATS["fruit_red"])]):
        sphere(f"fruit_bowl_piece_{i}", (x, 2.30, 1.22), 0.085, mat, "details")
    cyl("napkin_dispenser_metal", (-2.78, 2.45, 1.22), 0.10, 0.18, MATS["metal"], vertices=16, collection="details")

    cyl("round_black_trash_can", (3.05, 2.62, 0.45), 0.24, 0.82, MATS["black"], vertices=24, collection="details")
    cyl("trash_can_metal_lid", (3.05, 2.62, 0.88), 0.25, 0.045, MATS["metal"], vertices=24, collection="details")

    add_bevel(cube("community_notice_board", (-3.71, 0.70, 1.55), (0.05, 1.55, 0.95), MATS["wood"], "details"), 0.015)
    for i, (y, z, mat) in enumerate([(0.22, 1.75, MATS["paper"]), (0.70, 1.40, MATS["chair_a"]), (1.18, 1.78, MATS["chair_b"])]):
        cube(f"notice_board_muted_flyer_{i}", (-3.76, y, z), (0.022, 0.30, 0.28), mat, "details")

    for i, x in enumerate([-2.4, -0.8, 0.8, 2.4]):
        cube(f"rectangular_led_panel_diffuser_{i}", (x, -0.25, 2.99), (1.02, 0.42, 0.035), MATS["led"], "lighting")
    for i, y in enumerate([-2.0, 2.0]):
        cube(f"warm_wall_sconce_lens_{i}", (-3.60, y, 2.05), (0.035, 0.40, 0.18), MATS["led"], "lighting")


def add_camera_and_world():
    bpy.ops.object.camera_add(location=(0, 5.6, 1.85), rotation=(math.radians(74), 0, math.radians(180)))
    cam = bpy.context.object
    cam.name = "cafeteria_rear_view_camera"
    cam.data.lens = 21
    bpy.context.scene.camera = cam
    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.samples = 64
    bpy.context.scene.view_settings.view_transform = "Filmic"
    bpy.context.scene.view_settings.look = "Medium High Contrast"
    bpy.context.scene.world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world.color = (0.055, 0.060, 0.065)


def add_text_labels():
    bpy.ops.object.text_add(location=(-1.35, -3.36, 2.55), rotation=(math.radians(90), 0, 0))
    text = bpy.context.object
    text.name = "service_wall_text_cafeteria"
    text.data.body = "CAFE"
    text.data.align_x = "CENTER"
    text.data.align_y = "CENTER"
    text.data.size = 0.34
    text.data.extrude = 0.004
    text.data.materials.append(MATS["paper"])
    link_to_collection(text, "service_counter")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reset_scene()
    init_materials()
    add_room_shell()
    add_service_counter()
    add_dining_area()
    add_details()
    add_text_labels()
    add_camera_and_world()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    print(f"Saved revised cafeteria scene to {BLEND_PATH}")


if __name__ == "__main__":
    main()
