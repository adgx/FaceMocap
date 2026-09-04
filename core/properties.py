import bpy
from bpy.props import BoolProperty


class FACEMOCAP_PG_settings(bpy.types.PropertyGroup):

    mirror_x: BoolProperty(
        name="Specchia X",
        description="Attiva se il modello si muove al contrario su sinistra/destra",
        default=False,
    )


def register():
    bpy.types.Scene.facemocap = bpy.props.PointerProperty(type=FACEMOCAP_PG_settings)


def unregister():
    del bpy.types.Scene.facemocap
