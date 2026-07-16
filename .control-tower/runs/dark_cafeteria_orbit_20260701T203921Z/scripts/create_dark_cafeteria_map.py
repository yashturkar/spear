import argparse
import json
import os
import posixpath

import unreal


parser = argparse.ArgumentParser()
parser.add_argument("--source-map-path", required=True)
parser.add_argument("--target-map-path", required=True)
parser.add_argument("--validation-report", required=True)
parser.add_argument("--replace-existing-map", action="store_true")
args = parser.parse_args()


HIDE_TOKENS = [
    "exterior_daylight_context",
    "pale_sky_strip_above_exterior_wall",
    "visible_through_windows",
    "distant_brick_building_seen_through_windows",
    "distant_exterior_brick_wall_visible_through_windows",
    "exterior_concrete_walk_visible_through_windows",
    "exterior_concrete_walk",
    "exterior_muted_shrub",
    "exterior_planter_box",
    "rectangular_led_panel_diffuser",
    "warm_wall_sconce_lens",
    "warm_diffused_led_lens",
]

ENVIRONMENT_CLASS_TOKENS = [
    "SkyAtmosphere",
    "AtmosphericFog",
    "ExponentialHeightFog",
    "VolumetricCloud",
    "SphereReflectionCapture",
    "BoxReflectionCapture",
    "PlanarReflection",
]


def log(message):
    unreal.log(f"[dark_cafeteria_map] {message}")


def warn(message):
    unreal.log_warning(f"[dark_cafeteria_map] {message}")


def try_set(obj, name, value):
    try:
        obj.set_editor_property(name=name, value=value)
        return True
    except Exception as exc:
        warn(f"Could not set {obj.get_class().get_name()}.{name}: {exc}")
        return False


def path_to_filename(asset_path):
    rel = asset_path
    if rel.startswith("/Game/"):
        rel = rel[len("/Game/"):]
    return os.path.join(
        unreal.Paths.project_content_dir(),
        rel + ".uasset")


def duplicate_map(source_map_path, target_map_path, replace_existing_map):
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path=target_map_path):
        if not replace_existing_map:
            raise AssertionError(
                f"Target map already exists: {target_map_path}. Pass --replace-existing-map to overwrite it.")
        log(f"Deleting existing target map: {target_map_path}")
        if not unreal.EditorAssetLibrary.delete_asset(asset_path_to_delete=target_map_path):
            raise AssertionError(f"Could not delete existing target map: {target_map_path}")

    target_dir = posixpath.dirname(target_map_path)
    unreal.EditorAssetLibrary.make_directory(directory_path=target_dir)
    log(f"Duplicating map: {source_map_path} -> {target_map_path}")
    duplicated = unreal.EditorAssetLibrary.duplicate_asset(
        source_asset_path=source_map_path,
        destination_asset_path=target_map_path)
    if not duplicated:
        raise AssertionError(f"Could not duplicate map: {source_map_path} -> {target_map_path}")
    unreal.EditorAssetLibrary.save_asset(asset_to_save=target_map_path, only_if_is_dirty=False)
    duplicated = None
    try:
        unreal.SystemLibrary.collect_garbage()
    except Exception as exc:
        warn(f"Could not force garbage collection after map duplication: {exc}")


def actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def component_names(component):
    names = [component.get_name(), component.get_class().get_name()]
    for prop in ["static_mesh", "material"]:
        try:
            value = component.get_editor_property(prop)
            if value is not None:
                names.append(value.get_path_name())
        except Exception:
            pass
    try:
        for material_index in range(component.get_num_materials()):
            material = component.get_material(material_index)
            if material is not None:
                names.append(material.get_path_name())
    except Exception:
        pass
    return names


def actor_search_text(actor):
    names = [
        actor_label(actor),
        actor.get_name(),
        actor.get_class().get_name(),
    ]
    for component in actor.get_components_by_class(unreal.ActorComponent):
        names.extend(component_names(component))
    return " ".join(names).lower()


def matches_any_token(text, tokens):
    text_lower = text.lower()
    return any(token.lower() in text_lower for token in tokens)


def hide_actor(actor):
    actor.set_actor_hidden_in_game(True)
    try:
        actor.set_is_temporarily_hidden_in_editor(True)
    except Exception:
        pass
    try:
        actor.set_actor_enable_collision(False)
    except Exception:
        pass
    hidden_components = 0
    for component in actor.get_components_by_class(unreal.PrimitiveComponent):
        try_set(component, "visible", False)
        try_set(component, "hidden_in_game", True)
        try:
            component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        except Exception:
            pass
        hidden_components += 1
    return hidden_components


def hide_component(component):
    try_set(component, "visible", False)
    try_set(component, "hidden_in_game", True)
    try:
        component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    except Exception:
        pass


def make_light_movable(component):
    ok = False
    mobility = getattr(unreal.ComponentMobility, "MOVABLE", None)
    if mobility is not None:
        ok = try_set(component, "mobility", mobility) or ok
    ok = try_set(component, "cast_static_shadows", False) or ok
    ok = try_set(component, "cast_dynamic_shadows", True) or ok
    ok = try_set(component, "indirect_lighting_intensity", 0.0) or ok
    return ok


def configure_world_for_dynamic_lighting():
    world = unreal.EditorLevelLibrary.get_editor_world()
    world_settings = world.get_world_settings()
    results = {
        "force_no_precomputed_lighting_set": try_set(
            world_settings, "force_no_precomputed_lighting", True),
        "map_build_data_cleared": try_set(world, "map_build_data", None),
    }
    try:
        results["force_no_precomputed_lighting_readback"] = bool(
            world_settings.get_editor_property("force_no_precomputed_lighting"))
    except Exception as exc:
        results["force_no_precomputed_lighting_readback_error"] = str(exc)
    return results


def process_level():
    report = {
        "source_map_path": args.source_map_path,
        "target_map_path": args.target_map_path,
        "target_map_exists": unreal.EditorAssetLibrary.does_asset_exist(args.target_map_path),
        "target_map_file": path_to_filename(args.target_map_path),
        "world_settings": configure_world_for_dynamic_lighting(),
        "hidden_actor_labels": [],
        "hidden_component_labels": [],
        "environment_actor_labels": [],
        "light_components_made_movable": [],
        "remaining_visible_token_matches": [],
        "counts": {},
    }

    actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
    hidden_component_count = 0
    for actor in actors:
        text = actor_search_text(actor)
        class_name = actor.get_class().get_name()
        label = actor_label(actor)

        if matches_any_token(class_name, ENVIRONMENT_CLASS_TOKENS):
            hidden_component_count += hide_actor(actor)
            report["environment_actor_labels"].append(label)
            continue

        if matches_any_token(text, HIDE_TOKENS):
            hidden_component_count += hide_actor(actor)
            report["hidden_actor_labels"].append(label)
            continue

        for component in actor.get_components_by_class(unreal.PrimitiveComponent):
            names = " ".join(component_names(component))
            if matches_any_token(names, HIDE_TOKENS):
                hide_component(component)
                hidden_component_count += 1
                report["hidden_component_labels"].append(f"{label}:{component.get_name()}")

        for light_component in actor.get_components_by_class(unreal.LightComponentBase):
            if make_light_movable(light_component):
                report["light_components_made_movable"].append(
                    f"{label}:{light_component.get_class().get_name()}:{light_component.get_name()}")

    visible_token_matches = []
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        text = actor_search_text(actor)
        if matches_any_token(text, HIDE_TOKENS):
            visible = True
            try:
                visible = not actor.is_hidden_ed() and not actor.is_hidden()
            except Exception:
                pass
            if visible:
                visible_token_matches.append(actor_label(actor))

    report["remaining_visible_token_matches"] = sorted(visible_token_matches)
    report["counts"] = {
        "actors_total": len(actors),
        "hidden_actors": len(report["hidden_actor_labels"]),
        "environment_actors_hidden": len(report["environment_actor_labels"]),
        "hidden_components": hidden_component_count,
        "light_components_made_movable": len(report["light_components_made_movable"]),
        "remaining_visible_token_matches": len(report["remaining_visible_token_matches"]),
    }
    return report


if __name__ == "__main__":
    duplicate_map(
        source_map_path=args.source_map_path,
        target_map_path=args.target_map_path,
        replace_existing_map=args.replace_existing_map)

    level_editor_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    loaded = level_editor_subsystem.load_level(asset_path=args.target_map_path)
    if not loaded:
        raise AssertionError(f"Could not load target map: {args.target_map_path}")

    report = process_level()

    log(f"Saving dark map: {args.target_map_path}")
    saved = level_editor_subsystem.save_current_level()
    if not saved:
        raise AssertionError(f"Could not save target map: {args.target_map_path}")
    unreal.EditorAssetLibrary.save_directory(
        directory_path=posixpath.dirname(args.target_map_path),
        only_if_is_dirty=False,
        recursive=True)

    os.makedirs(os.path.dirname(args.validation_report), exist_ok=True)
    with open(args.validation_report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    log(f"Wrote validation report: {args.validation_report}")
    log(json.dumps(report, indent=2, sort_keys=True))
