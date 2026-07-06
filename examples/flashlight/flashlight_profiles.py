#
# Copyright (c) 2025 The SPEAR Development Team. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
#

from __future__ import annotations

import copy
import json
import math
import os


DEFAULT_PROFILE_FILE = os.path.realpath(os.path.join(os.path.dirname(__file__), "flashlight_profiles.json"))
NUMERIC_PROFILE_FIELDS = (
    "intensity",
    "attenuation_radius",
    "indirect_lighting_intensity",
    "inner_cone_angle",
    "outer_cone_angle",
    "source_radius",
    "soft_source_radius",
    "contact_shadow_length",
)
BOOLEAN_PROFILE_FIELDS = (
    "cast_shadows",
    "cast_dynamic_shadows",
    "contact_shadows",
)
CLI_FLAG_BY_FIELD = {
    "intensity": "--intensity",
    "attenuation_radius": "--attenuation-radius",
    "indirect_lighting_intensity": "--indirect-lighting-intensity",
    "inner_cone_angle": "--inner-cone-angle",
    "outer_cone_angle": "--outer-cone-angle",
    "source_radius": "--source-radius",
    "soft_source_radius": "--soft-source-radius",
    "contact_shadow_length": "--contact-shadow-length",
    "cast_shadows": ("--enable-flashlight-shadows", "--disable-flashlight-shadows"),
    "cast_dynamic_shadows": ("--enable-flashlight-dynamic-shadows", "--disable-flashlight-dynamic-shadows"),
    "contact_shadows": ("--enable-flashlight-contact-shadows", "--disable-flashlight-contact-shadows"),
}


def add_flashlight_profile_args(parser):
    parser.add_argument("--flashlight-profile", default=None)
    parser.add_argument("--flashlight-profile-file", default=DEFAULT_PROFILE_FILE)
    shadow_group = parser.add_mutually_exclusive_group()
    shadow_group.add_argument("--enable-flashlight-shadows", dest="cast_shadows", action="store_true", default=None)
    shadow_group.add_argument("--disable-flashlight-shadows", dest="cast_shadows", action="store_false")
    dynamic_shadow_group = parser.add_mutually_exclusive_group()
    dynamic_shadow_group.add_argument("--enable-flashlight-dynamic-shadows", dest="cast_dynamic_shadows", action="store_true", default=None)
    dynamic_shadow_group.add_argument("--disable-flashlight-dynamic-shadows", dest="cast_dynamic_shadows", action="store_false")
    contact_shadow_group = parser.add_mutually_exclusive_group()
    contact_shadow_group.add_argument("--enable-flashlight-contact-shadows", dest="contact_shadows", action="store_true", default=None)
    contact_shadow_group.add_argument("--disable-flashlight-contact-shadows", dest="contact_shadows", action="store_false")
    parser.add_argument("--contact-shadow-length", type=float, default=None)


def get_explicit_cli_flags(argv):
    return {
        arg.split("=", 1)[0]
        for arg in argv
        if arg.startswith("--")
    }


def load_profile_document(profile_file):
    with open(profile_file, "r", encoding="utf-8") as f:
        document = json.load(f)
    if not isinstance(document, dict):
        raise ValueError("Flashlight profile file must contain a JSON object.")
    if document.get("schema_version") != "1.0.0":
        raise ValueError("Flashlight profile file schema_version must be 1.0.0.")
    if not isinstance(document.get("profiles"), dict) or not document["profiles"]:
        raise ValueError("Flashlight profile file must contain a non-empty profiles object.")
    default_profile = document.get("default_profile")
    if not isinstance(default_profile, str) or default_profile not in document["profiles"]:
        raise ValueError("Flashlight profile file default_profile must name an existing profile.")
    return document


def parse_finite_float(value, context, *, minimum=None, exclusive_minimum=False):
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} must be a finite number.") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{context} must be a finite number.")
    if minimum is not None:
        if exclusive_minimum and parsed <= minimum:
            raise ValueError(f"{context} must be greater than {minimum}.")
        if not exclusive_minimum and parsed < minimum:
            raise ValueError(f"{context} must be greater than or equal to {minimum}.")
    return parsed


def compute_outer_cone_angle_from_beam(beam):
    if not isinstance(beam, dict):
        raise ValueError("Flashlight profile beam must be an object.")
    diameter = parse_finite_float(beam.get("diameter"), "Flashlight profile beam diameter", minimum=0.0, exclusive_minimum=True)
    distance = parse_finite_float(beam.get("distance"), "Flashlight profile beam distance", minimum=0.0, exclusive_minimum=True)
    units = beam.get("units", "unitless")
    if not isinstance(units, str) or not units:
        raise ValueError("Flashlight profile beam units must be a non-empty string.")
    return math.degrees(math.atan((diameter * 0.5) / distance))


def normalize_profile(profile_name, profile):
    if not isinstance(profile, dict):
        raise ValueError(f"Flashlight profile {profile_name} must be an object.")
    normalized = copy.deepcopy(profile)
    if "outer_cone_angle" not in normalized:
        if "beam" not in normalized:
            raise ValueError(f"Flashlight profile {profile_name} must define outer_cone_angle or beam.")
        normalized["outer_cone_angle"] = compute_outer_cone_angle_from_beam(normalized["beam"])
    for field in NUMERIC_PROFILE_FIELDS:
        if field not in normalized:
            raise ValueError(f"Flashlight profile {profile_name} is missing {field}.")
        minimum = 0.0
        exclusive = field == "attenuation_radius"
        normalized[field] = parse_finite_float(
            normalized[field],
            f"Flashlight profile {profile_name} {field}",
            minimum=minimum,
            exclusive_minimum=exclusive)
    if normalized["outer_cone_angle"] < normalized["inner_cone_angle"]:
        raise ValueError(f"Flashlight profile {profile_name} outer_cone_angle must be >= inner_cone_angle.")
    for field in BOOLEAN_PROFILE_FIELDS:
        if field not in normalized:
            raise ValueError(f"Flashlight profile {profile_name} is missing {field}.")
        if not isinstance(normalized[field], bool):
            raise ValueError(f"Flashlight profile {profile_name} {field} must be a JSON boolean.")
    return normalized


def field_was_explicit(field, explicit_flags):
    flags = CLI_FLAG_BY_FIELD[field]
    if isinstance(flags, tuple):
        return any(flag in explicit_flags for flag in flags)
    return flags in explicit_flags


def apply_profile_to_args(args, argv):
    explicit_flags = get_explicit_cli_flags(argv)
    document = load_profile_document(args.flashlight_profile_file)
    profile_name = args.flashlight_profile or document["default_profile"]
    profiles = document["profiles"]
    if profile_name not in profiles:
        raise ValueError(f"Unknown flashlight profile: {profile_name}")
    profile = normalize_profile(profile_name=profile_name, profile=profiles[profile_name])

    for field in NUMERIC_PROFILE_FIELDS + BOOLEAN_PROFILE_FIELDS:
        if getattr(args, field, None) is None or not field_was_explicit(field, explicit_flags):
            setattr(args, field, profile[field])

    args.flashlight_profile = profile_name
    args.flashlight_profile_desc = {
        "profile_file": os.path.realpath(args.flashlight_profile_file),
        "profile_name": profile_name,
        "profile": profile,
        "explicit_cli_flags": sorted(explicit_flags),
    }
    return args


def get_resolved_flashlight_settings(args):
    return {
        "profile_file": os.path.realpath(args.flashlight_profile_file),
        "profile_name": args.flashlight_profile,
        "intensity": float(args.intensity),
        "attenuation_radius": float(args.attenuation_radius),
        "indirect_lighting_intensity": float(args.indirect_lighting_intensity),
        "inner_cone_angle": float(args.inner_cone_angle),
        "outer_cone_angle": float(args.outer_cone_angle),
        "source_radius": float(args.source_radius),
        "soft_source_radius": float(args.soft_source_radius),
        "cast_shadows": bool(args.cast_shadows),
        "cast_dynamic_shadows": bool(args.cast_dynamic_shadows),
        "contact_shadows": bool(args.contact_shadows),
        "contact_shadow_length": float(args.contact_shadow_length),
    }


def try_call_method(obj, method_name, **kwargs):
    method = getattr(obj, method_name, None)
    if method is None:
        call = getattr(obj, "call", None)
        if call is None:
            return False
        try:
            call(method_name, args=kwargs)
        except Exception:
            return False
        return True
    try:
        method(**kwargs)
    except TypeError:
        try:
            method(*kwargs.values())
        except Exception:
            return False
    except Exception:
        return False
    return True


def try_call_any_method(obj, method_name, value):
    for key in ("bNewValue", "NewValue", "Value", "bEnabled", "Enabled"):
        if try_call_method(obj, method_name, **{key: value}):
            return True
    return False


def apply_spot_light_shadow_controls(spot_light_component, args):
    state = {
        "cast_shadows_set": False,
        "cast_dynamic_shadows_set": False,
        "contact_shadows_set": False,
        "contact_shadow_length_set": False,
    }
    state["cast_shadows_set"] = try_call_any_method(
        spot_light_component,
        "SetCastShadows",
        args.cast_shadows)
    state["cast_dynamic_shadows_set"] = state["cast_shadows_set"]
    if args.contact_shadows:
        state["contact_shadow_length_set"] = try_call_any_method(
            spot_light_component,
            "SetContactShadowLength",
            args.contact_shadow_length)
        state["contact_shadows_set"] = state["contact_shadow_length_set"]
    return state
