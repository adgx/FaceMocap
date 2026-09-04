import bpy

from ..core.config import FACE_MAPPING
from ..core.rig import RIG_NAME, create_bones


class FACEMOCAP_OT_create_armature(bpy.types.Operator):
    """Genera l'armatura facciale di riferimento per il motion capture"""
    bl_idname = "facemocap.create_armature"
    bl_label = "Crea Armatura Base"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Crea l'armatura
        arm_data = bpy.data.armatures.new(name="FaceMocap_Arm_Data")
        arm_obj = bpy.data.objects.new(name=RIG_NAME, object_data=arm_data)

        # collega l'armatura alla scena
        context.collection.objects.link(arm_obj)

        # seleziona armatura
        bpy.ops.object.select_all(action='DESELECT')
        arm_obj.select_set(True)
        context.view_layer.objects.active = arm_obj

        bpy.ops.object.mode_set(mode='EDIT')

        # Armatura di riferimento
        create_bones(
            arm_data.edit_bones,
            adapt=lambda pos: pos,
            tail_length=lambda name: 0.6 if name == "Head" else 0.1,
        )

        bpy.ops.object.mode_set(mode='OBJECT')

        arm_obj.show_in_front = True

        self.report({'INFO'}, "Armatura generata con %d ossa!" % len(FACE_MAPPING))

        return {'FINISHED'}
