import bpy

from .rig import LANDMARKS_RIG_NAME, ADVANCED_RIG_NAME
from . import config
from bpy.types import PropertyGroup
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty
)

#added
class FACEMOCAP_PG_mapping(bpy.types.PropertyGroup):
    role: StringProperty(name="Role", "Role defines which part of the face to control")
    target_bone: StringProperty(name="Target Bone")
    source_bones: StringProperty(name="Source Bones")
    mode: EnumProperty(name="Mode", 
                       items=[
                           ("TRANSLATION", "Translation", "Translate target bone"),
                           ("ROTATION", "Rotation", "Rotate target bone")
                       ],
                       default="TRANSLATION")
    gain: FloatProperty(name="Gain", default=1.0, min=0.0, max=10.0)
    enabled: BoolProperty(name="Enabled", default=True)

class FACEMOCAP_PG_settings(bpy.types.PropertyGroup):
    source_rig_name: StringProperty(name="Source Rig", default=LANDMARKS_RIG_NAME)
    source_rig_name: StringProperty(name="Target Rig", default=ADVANCED_RIG_NAME)
    camera_id: IntProperty(name="Camera", default=0, min=0, max=20)
    smoothing: FloatProperty(name="Smoothing", default=config.SMOOTHING, min=0.0, max=0.99)
    #we could add the aspect ratio
    mirror_x: BoolProperty(
        name="Mirror X axis",
        description="Attiva se il modello si muove al contrario su sinistra/destra",
        default=False,
    )
    mappings: CollectionProperty(type=FACEMOCAP_PG_mapping)
    mapping_index: IntProperty(default=0)

def populate_default_mapping(settings):
    settings.mappings.clear()

    for(role, reTargetMap) in config.DEFAULT_RETARGET_MAP.items():
        item = settings.mappings.add()
        item.role = role
        item.target_bone = reTargetMap.target
        item.source_bones = reTargetMap.source
        item.mode = reTargetMap.mode
        item.gain = reTargetMap.gain
        item.enabled = reTargetMap.enable

def ensure_mapping(settings):
    if len(settings.mappings) == 0:
        populate_default_mapping(settings)


classes = (FACEMOCAP_PG_mapping, FACEMOCAP_PG_settings)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.facemocap = bpy.props.PointerProperty(type=FACEMOCAP_PG_settings)


def unregister():
    del bpy.types.Scene.facemocap

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
