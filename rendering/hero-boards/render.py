import argparse
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


SCRIPT_DIR = Path(__file__).resolve().parent


BOARD_SPECS = (
    {
        "name": "RP2040",
        "filename": "rp2040-blue-soldermask.glb",
        "target_width": 3.30,
        "center": (-0.95, 1.05, 0.10),
        "rotation": 45.0,
    },
    {
        "name": "Game Boy",
        "filename": "gameboy.glb",
        "target_width": 4.30,
        "center": (4.35, 3.55, 0.00),
        "rotation": 45.0,
    },
    {
        "name": "nRF52810",
        "filename": "nrf52810.glb",
        "target_width": 3.40,
        "center": (4.20, -3.15, 0.15),
        "rotation": 45.0,
    },
    {
        "name": "Attiny85 Arcade Keychain",
        "filename": "attiny85-arcade-keychain.glb",
        "target_width": 3.80,
        "center": (-3.65, -2.45, 0.08),
        "rotation": 0.0,
    },
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models-dir", default=str(SCRIPT_DIR / "models"))
    parser.add_argument(
        "--output",
        default=str(SCRIPT_DIR.parent.parent / "assets" / "hero-board-four-real-3d.png"),
    )
    parser.add_argument("--samples", type=int, default=96)
    parser.add_argument("--engine", choices=("eevee", "cycles"), default="cycles")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def reset_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def get_bounds(objects):
    minimum = Vector((math.inf, math.inf, math.inf))
    maximum = Vector((-math.inf, -math.inf, -math.inf))
    for obj in objects:
        if obj.type != "MESH" or not obj.visible_get():
            continue
        for corner in obj.bound_box:
            point = obj.matrix_world @ Vector(corner)
            minimum.x = min(minimum.x, point.x)
            minimum.y = min(minimum.y, point.y)
            minimum.z = min(minimum.z, point.z)
            maximum.x = max(maximum.x, point.x)
            maximum.y = max(maximum.y, point.y)
            maximum.z = max(maximum.z, point.z)
    return minimum, maximum


def principled_input(node, *names):
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None:
            return socket
    return None


def set_socket(node, value, *names):
    socket = principled_input(node, *names)
    if socket is not None and not socket.is_linked:
        socket.default_value = value


def material_base_color(material):
    if not material.use_nodes or not material.node_tree:
        return tuple(material.diffuse_color[:3])
    principled = next(
        (node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"),
        None,
    )
    if principled is None:
        return tuple(material.diffuse_color[:3])
    base = principled_input(principled, "Base Color")
    return tuple(base.default_value[:3]) if base else tuple(material.diffuse_color[:3])


def is_board_material(material):
    name = material.name.lower()
    return any(
        board_name in name
        for board_name in ("topmaterial", "bottommaterial", "boardsidematerial")
    )


def is_board_object(obj):
    return any(
        slot.material and is_board_material(slot.material)
        for slot in obj.material_slots
    )


def configure_component_materials():
    for material in bpy.data.materials:
        if is_board_material(material):
            continue
        material.use_nodes = True
        nodes = material.node_tree.nodes if material.node_tree else []
        principled = next(
            (node for node in nodes if node.type == "BSDF_PRINCIPLED"), None
        )
        if principled is None:
            continue
        color = material_base_color(material)
        luminance = 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]
        chroma = max(color) - min(color)
        looks_gold = color[0] > 0.55 and color[1] > 0.35 and color[2] < 0.35
        looks_dark = luminance < 0.28
        looks_light = luminance > 0.72 and chroma < 0.2
        if looks_gold:
            set_socket(principled, 0.24, "Roughness")
            set_socket(principled, 0.78, "Metallic")
        elif looks_dark:
            set_socket(principled, 0.34, "Roughness")
            set_socket(principled, 0.06, "Metallic")
            set_socket(principled, 0.06, "Coat Weight", "Clearcoat")
        elif looks_light:
            set_socket(principled, 0.42, "Roughness")
            set_socket(principled, 0.08, "Metallic")
            set_socket(principled, 0.05, "Coat Weight", "Clearcoat")
        else:
            set_socket(principled, 0.48, "Roughness")
            set_socket(principled, 0.16, "Metallic")


def improve_component_normals(objects):
    for obj in objects:
        if obj.type != "MESH" or is_board_object(obj):
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        try:
            if obj.data.users > 1:
                obj.data = obj.data.copy()
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.remove_doubles(threshold=0.00001)
            bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.shade_smooth_by_angle()
            modifier = obj.modifiers.new(
                name="Manufactured package normals", type="WEIGHTED_NORMAL"
            )
            modifier.keep_sharp = True
            modifier.mode = "FACE_AREA"
            modifier.thresh = 0.01
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        except Exception as error:
            if obj.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            print("NORMAL_FALLBACK", obj.name, error)


def import_and_place(spec, models_dir):
    filepath = os.path.join(models_dir, spec["filename"])
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(filepath))
    imported = [obj for obj in bpy.context.scene.objects if obj not in before]
    minimum, maximum = get_bounds(imported)
    source_center = (minimum + maximum) * 0.5
    source_width = maximum.x - minimum.x
    root = bpy.data.objects.new(f'{spec["name"]} presentation root', None)
    bpy.context.scene.collection.objects.link(root)
    root.location = source_center
    imported_set = set(imported)
    for obj in [obj for obj in imported if obj.parent not in imported_set]:
        world_transform = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_world = world_transform
    scale = spec["target_width"] / source_width
    root.scale = (scale, scale, scale)
    root.rotation_euler = (0.0, 0.0, math.radians(spec["rotation"]))
    root.location = spec["center"]
    print("PLACED", spec["name"], filepath, "scale", round(scale, 6))
    return imported


def point_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def add_area_light(name, location, target, color, energy, size):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.color = color
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name=name, object_data=data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    point_at(obj, target)


def add_spot_light(name, location, target, color, energy):
    data = bpy.data.lights.new(name=name, type="SPOT")
    data.color = color
    data.energy = energy
    data.shadow_soft_size = 2.1
    data.spot_size = math.radians(46.0)
    data.spot_blend = 0.78
    obj = bpy.data.objects.new(name=name, object_data=data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    point_at(obj, target)


def configure_scene(args):
    scene = bpy.context.scene
    scene.render.engine = (
        "BLENDER_EEVEE_NEXT" if args.engine == "eevee" else "CYCLES"
    )
    if args.engine == "cycles":
        scene.cycles.samples = args.samples
        scene.cycles.use_denoising = True
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = 0.018
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1500
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.filepath = os.path.abspath(args.output)

    camera_data = bpy.data.cameras.new("Hero orthographic camera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 15.4
    camera = bpy.data.objects.new("Hero orthographic camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0.4, 0.0, 30.0)
    camera.rotation_euler = (0.0, 0.0, 0.0)
    scene.camera = camera

    for spec in BOARD_SPECS:
        center = spec["center"]
        add_spot_light(
            f'{spec["name"]} off-center warm key',
            (center[0] - 1.8, center[1] + 2.0, 9.5),
            (center[0] - 0.55, center[1] + 0.55, 0.0),
            (1.0, 0.92, 0.82),
            820.0,
        )
    add_area_light(
        "Shared cool fill",
        (8.0, -7.0, 15.0),
        (0.0, 0.0, 0.0),
        (0.72, 0.84, 1.0),
        430.0,
        11.0,
    )
    add_area_light(
        "Shared mint rim",
        (7.0, 8.5, 10.0),
        (0.0, 0.5, 0.0),
        (0.66, 1.0, 0.82),
        240.0,
        7.0,
    )
    world = scene.world or bpy.data.worlds.new("Neutral studio world")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.74, 0.78, 0.84, 1.0)
    background.inputs["Strength"].default_value = 0.28


def main():
    args = parse_args()
    reset_scene()
    imported = []
    for spec in BOARD_SPECS:
        imported.extend(import_and_place(spec, args.models_dir))
    improve_component_normals(imported)
    configure_component_materials()
    configure_scene(args)
    bpy.ops.render.render(write_still=True)
    print("RENDERED", os.path.abspath(args.output))


if __name__ == "__main__":
    main()
