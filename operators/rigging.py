import bpy

from ..core.config import FACE_MAPPING, LANDMARKERS_FACE_MAPPING
from ..core.rig import RIG_NAME, LANDMARKS_RIG_NAME, create_bones

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
            arm_data,
            adapt=lambda pos: pos,
            tail_length=lambda name: 0.6 if name == "Head" else 0.1,
        )

        bpy.ops.object.mode_set(mode='OBJECT')

        arm_obj.show_in_front = True

        self.report({'INFO'}, "Armatura generata con %d ossa!" % len(FACE_MAPPING))

        return {'FINISHED'}

class FACEMOCAP_OT_create_advance_armature(bpy.types.Operator):
    """Genera l'armatura facciale di riferimento per il motion capture
       Generate the advance facial armature
    """
    bl_idname = "facemocap.create_advance_armature"
    bl_label = "Generate Advance Facial Armature"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        #create the collection
        parent_collection = context.collection

        if parent_collection is None:
            self.report({'ERROR'}, "No active collection")
            return {'CANCELLED'}
        
        FM_facial_coll_name = "FaceMocap-Facial_rig"
        FM_facial_coll = bpy.data.collections.new(FM_facial_coll_name)
        parent_collection.children.link(FM_facial_coll)

        #add armature
        arm_name = LANDMARKS_RIG_NAME
        arm_data = bpy.data.armatures.new(arm_name)
        arm_data.display_type = 'BBONE'
        arm_obj = bpy.data.objects.new(arm_name, arm_data)

        FM_facial_coll.objects.link(arm_obj)

        #select the arm
        bpy.ops.object.select_all(action='DESELECT')
        arm_obj.select_set(True)
        context.view_layer.objects.active = arm_obj

        bpy.ops.object.mode_set(mode='EDIT')

        create_bones(
            arm_data,
            adapt=lambda pos: pos,
            tail_length=lambda name: 0.6 if name == "Head" else 0.1,
            advance=True
        )

        bpy.ops.object.mode_set(mode='OBJECT')

        arm_obj.show_in_front = True

        self.report({'INFO'}, "Armatura generata")

        return {'FINISHED'}