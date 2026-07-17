import bpy

class FACEMOCAP_OT_create_armature(bpy.types.Operator):
    """Genera l'armatura facciale di riferimento per il motion capture"""
    bl_idname = "facemocap.create_armature"
    bl_label = "Crea Armatura Base"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Crea l'armatura
        arm_data = bpy.data.armatures.new(name="FaceMocap_Arm_Data")
        arm_obj = bpy.data.objects.new(name="FaceMocap_Rig", object_data=arm_data)
        
        # collega l'armatura alla scena
        context.collection.objects.link(arm_obj)
        
        # seleziona armatura
        bpy.ops.object.select_all(action='DESELECT')
        arm_obj.select_set(True)
        context.view_layer.objects.active = arm_obj
        
        bpy.ops.object.mode_set(mode='EDIT')
        
        # Osso della testa
        head_bone = arm_data.edit_bones.new("Head")
        head_bone.head = (0.0, 0.0, 0.0)
        head_bone.tail = (0.0, 0.0, 0.5)
        
        # Osso della mandibola
        jaw_bone = arm_data.edit_bones.new("Jaw")
        jaw_bone.head = (0.0, -0.05, 0.1)
        jaw_bone.tail = (0.0, -0.2, 0.0)
        jaw_bone.parent = head_bone

        # Ossa per movimento bocca
        mouth_l_bone = arm_data.edit_bones.new("Mouth_Corner_L")
        mouth_l_bone.head = (0.12, -0.12, 0.1)
        mouth_l_bone.tail = (0.12, -0.22, 0.1)
        mouth_l_bone.parent = jaw_bone
        
        mouth_r_bone = arm_data.edit_bones.new("Mouth_Corner_R")
        mouth_r_bone.head = (-0.12, -0.12, 0.1)
        mouth_r_bone.tail = (-0.12, -0.22, 0.1)
        mouth_r_bone.parent = jaw_bone

        #Osso Naso
        nose_bone = arm_data.edit_bones.new("Nose")
        nose_bone.head = (0.0, -0.15, 0.25)
        nose_bone.tail = (0.0, -0.25, 0.25)
        nose_bone.parent = head_bone
        
        # Osso occhio sx
        eye_l_bone = arm_data.edit_bones.new("Eye_L")
        eye_l_bone.head = (0.15, -0.1, 0.3)
        eye_l_bone.tail = (0.15, -0.2, 0.3)
        eye_l_bone.parent = head_bone
        
        # Osso occhio dx
        eye_r_bone = arm_data.edit_bones.new("Eye_R")
        eye_r_bone.head = (-0.15, -0.1, 0.3)
        eye_r_bone.tail = (-0.15, -0.2, 0.3)
        eye_r_bone.parent = head_bone

        #Sopracciglia sx
        brow_l_bone = arm_data.edit_bones.new("Brow_L")
        brow_l_bone.head = (0.15, -0.12, 0.45)
        brow_l_bone.tail = (0.15, -0.22, 0.45)
        brow_l_bone.parent = head_bone
        
        #sopracciglia dx
        brow_r_bone = arm_data.edit_bones.new("Brow_R")
        brow_r_bone.head = (-0.15, -0.12, 0.45)
        brow_r_bone.tail = (-0.15, -0.22, 0.45)
        brow_r_bone.parent = head_bone

        bpy.ops.object.mode_set(mode='OBJECT')
        
        arm_obj.show_in_front = True
        
        self.report({'INFO'}, "Armatura generata con successo!")
        
        return {'FINISHED'}