import bpy

from .config import FACE_MAPPING, ROTATION_BONES

RIG_NAME = "FaceMocap_Rig"


def find_rig(context=None):
    """L'armatura del rig, o None. Cercata per nome o per armatura attiva"""
    obj = bpy.data.objects.get(RIG_NAME)
    if obj is not None and obj.type == 'ARMATURE':
        return obj
    if context is not None:
        active = context.active_object
        if active is not None and active.type == 'ARMATURE':
            return active
    return None


def create_bones(edit_bones, adapt, tail_length):
    """Crea ossa e parentele dell'intero rig. L'armatura dev'essere in Edit Mode."""
    for name, data in FACE_MAPPING.items():
        bone = edit_bones.new(name)

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
            edit_bones[name].parent = edit_bones[data.parent_bone]
