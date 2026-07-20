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
        
        bones_setup = {
            "Head":           (0.0,  0.0,  0.0),
            "Jaw":            (0.0, -0.1, -0.5),
            "Eye_L":          (0.2, -0.2,  0.2),
            "Eye_R":         (-0.2, -0.2,  0.2),
            "Brow_L":         (0.2, -0.25, 0.4),
            "Brow_R":        (-0.2, -0.25, 0.4),
            "Mouth_Corner_L": (0.15, -0.15, -0.3),
            "Mouth_Corner_R":(-0.15, -0.15, -0.3)
        }
        
        edit_bones = arm_data.edit_bones

        for name, pos in bones_setup.items():
            b = edit_bones.new(name)
            b.head = pos
            b.tail = (pos[0], pos[1], pos[2] + 0.1) 
            
            if name == "Head":
                b.tail = (pos[0], pos[1], pos[2] + 0.6)

        # imparentazione delle ossa
        edit_bones["Jaw"].parent = edit_bones["Head"]
        edit_bones["Eye_L"].parent = edit_bones["Head"]
        edit_bones["Eye_R"].parent = edit_bones["Head"]
        edit_bones["Brow_L"].parent = edit_bones["Head"]
        edit_bones["Brow_R"].parent = edit_bones["Head"]
        
        edit_bones["Mouth_Corner_L"].parent = edit_bones["Jaw"]
        edit_bones["Mouth_Corner_R"].parent = edit_bones["Jaw"]

        bpy.ops.object.mode_set(mode='OBJECT')
        
        arm_obj.show_in_front = True
        
        self.report({'INFO'}, "Armatura generata con successo!")
        
        return {'FINISHED'}