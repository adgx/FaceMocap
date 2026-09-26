import bpy

from mathutils import Vector, Matrix

BASE_RIG_NAME = "RIG-FaceMocap_base"
TARGET_RIG_NAME = "RIG-FaceMocap_advanced_face"
LANDMARKS_RIG_NAME = "RIG-FaceMocap_Landmarkers"

from .config import FACE_MAPPING, ROTATION_BONES, LANDMARKERS_FACE_MAPPING
from .solver import traslation_to_bone_space

#it could make sense to use a distintion between the sorce, and target rig   
def find_rig(context=None, name_rig: str =""):
    """L'armatura del rig, o None. Cercata per nome o per armatura attiva"""

    if not name_rig.__len__():
        obj = bpy.data.objects.get(BASE_RIG_NAME)
        if (obj is None) or obj.type == "ARMATURE":
                return None
        return obj

    obj = bpy.data.objects.get(name_rig)
    if obj is not None and obj.type == 'ARMATURE':
        return obj
    
    return None


def create_bones(arm_data, adapt, tail_length, advance: bool = False):
    """Crea ossa e parentele dell'intero rig. L'armatura dev'essere in Edit Mode."""
    if advance:
        create_landmarkers_bone(arm_data, adapt)
        return

    for name, data in FACE_MAPPING.items():
        bone = arm_data.edit_bones.new(name)

        if name in ROTATION_BONES:
            # ossa dellan mandibola: testa sul perno, coda sul mento.
            head_pos, tail_pos = ROTATION_BONES[name]
            bone.head = adapt(head_pos)
            bone.tail = adapt(tail_pos)
            continue

        x, y, z = adapt(data.position)
        bone.head = (x, y, z)
        bone.tail = (x, y, z + tail_length(name))

    for name, data in FACE_MAPPING.items():
        if data.parent_bone:
            arm_data.edit_bones[name].parent = arm_data.edit_bones[data.parent_bone]

def create_landmarkers_bone(arm_data, adapt):
    """Make the landmarkers rig"""
    #fixed properties for each bone
    tail_len = 0.008
    bbone_x = 0.004
    bbone_z = 0.003

    #make the root
    root_bone = arm_data.edit_bones.new("LMK-Root")
    root_bone.head = (0, 0, 0)
    root_bone.tail = (0, 0, tail_len)
    root_bone.bbone_x = bbone_x
    root_bone.bbone_z = bbone_z

    for name, data in LANDMARKERS_FACE_MAPPING.items():
        bone = arm_data.edit_bones.new(name)

        x, y, z = adapt(data.position)
        bone.head = (x, y, z)
        bone.tail = (x, y, z + tail_len)
        bone.bbone_x = bbone_x
        bone.bbone_z = bbone_z
        bone.parent =  root_bone

    bpy.ops.object.mode_set(mode='OBJECT')

    # Assign display color afterwards
    for bone in arm_data.bones:
        bone.color.palette = 'THEME07'

#added
def apply_translation(pose_bone, vec):
    pose_bone.location = (traslation_to_bone_space(pose_bone=pose_bone, vec=vec))

#added
def apply_rotation(pose_bone, rotation):
    pose_bone.rotation_mode = "QUATERNION"
    pose_bone.rotation_quaternion = (rotation.to_quaternion())

#added
def validate_target(rig, mappings):
    if rig is None:
        return ["Target not found"]

    missing = []

    for mapping in mappings:
        if not mapping.enabled:
            continue

        name = mapping.target_bone

        if not name:
            continue

        if rig.pose.bones.get(name) is None:
            missing.append(name)

    return sorted(set(missing))

def reset_rig_pose(rig):
    """Riporta a riposo le ossa gestite dal mocap.
       Reset the bone location position and rotation
    """
    for pose_bone in rig.pose.bones.values():
        if not pose_bone:
            continue
        pose_bone.location = (0.0, 0.0, 0.0)
        if pose_bone.rotation_mode == 'QUATERNION':
            pose_bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        else:
            pose_bone.rotation_euler = (0.0, 0.0, 0.0)