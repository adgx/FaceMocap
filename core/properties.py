import bpy

from .rig import LANDMARKS_RIG_NAME, TARGET_RIG_NAME
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
    role: StringProperty(name="Role", description="Role defines which part of the face to control")
    target_bone: StringProperty(name="Target Bone")
    source_bones: StringProperty(name="Source Bones")
    mode: EnumProperty(name="Mode", 
                       items=[
                           ("TRANSLATION", "Translation", "Translate target bone"),
                           ("ROTATION", "Rotation", "Rotate target bone")
                       ],
                       default="TRANSLATION")
    gain: FloatProperty(name="Gain", description="Defines how much the source bones influence the target bone", default=1.0, min=0.0, max=10.0)
    enabled: BoolProperty(name="Enabled", default=True)

class FACEMOCAP_PG_settings(bpy.types.PropertyGroup):
    source_rig_name: StringProperty(name="Source Rig", description="Armature representing the motion capture data", default=LANDMARKS_RIG_NAME)
    target_rig_name: StringProperty(name="Target Rig", description="Target armature to which the motion capture data is applied", default=TARGET_RIG_NAME)
    camera_id: IntProperty(name="Camera ID", description="Specifies the ID of the camera to use",default=0, min=0, max=20)
    smoothing: FloatProperty(name="Smoothing", description="Defines the alpha value of the anti-jitter filter",default=config.SMOOTHING, min=0.0, max=0.99)
    #we could add the aspect ratio
    mirror_x: BoolProperty(
        name="Mirror X axis",
        #description="Attiva se il modello si muove al contrario su sinistra/destra",
        description="Enabled if left/right movement is reversed",
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
        item.source_bones = ", ".join(reTargetMap.source)
        item.mode = reTargetMap.mode.value
        item.gain = reTargetMap.gain
        item.enabled = reTargetMap.enable

def mapping_is_empty(settings):
    return len(settings.mappings) == 0


classes = (FACEMOCAP_PG_mapping, FACEMOCAP_PG_settings)

def register():
    bpy.types.Scene.facemocap = bpy.props.PointerProperty(type=FACEMOCAP_PG_settings)


def unregister():
    del bpy.types.Scene.facemocap