import bpy
from ..core.webcam_core import FaceTracker 

class FACEMOCAP_OT_start_capture(bpy.types.Operator):
    """Avvia la motion capture facciale in background"""
    bl_idname = "facemocap.start_capture"
    bl_label = "Avvia Motion Capture"
    
    _timer = None
    _tracker = None
    
    def modal(self, context, event):
        #ESC o Tasto Destro per fermare la cattura
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel(context)
            return {'CANCELLED'}

        # si esegue ogni tot per non fare bloccare blender
        if event.type == 'TIMER':
            frame, results = self._tracker.read_frame()
            
            if results and results.multi_face_landmarks:
                landmarks = results.multi_face_landmarks[0].landmark
                
                arm_obj = bpy.data.objects.get("FaceMocap_Rig")
                
                if not arm_obj and context.active_object and context.active_object.type == 'ARMATURE':
                    arm_obj = context.active_object
                
                if arm_obj:
                    if context.active_object != arm_obj:
                        bpy.ops.object.select_all(action='DESELECT')
                        arm_obj.select_set(True)
                        context.view_layer.objects.active = arm_obj
                        
                    if context.mode != 'POSE':
                        bpy.ops.object.mode_set(mode='POSE')
                    

                    bone_map = {
                        "Head": (1, None),            # Punta del naso
                        "Jaw": (152, 1),              # Mento (relativo al naso)
                        "Eye_L": (159, 1),            # Occhio sx (bordo interno)
                        "Eye_R": (386, 1),            # Occhio dx (bordo interno)
                        "Brow_L": (105, 1),           # Sopracciglio sx
                        "Brow_R": (334, 1),           # Sopracciglio dx
                        "Mouth_Corner_L": (61, 152),  # Angolo bocca sx
                        "Mouth_Corner_R": (291, 152)  # Angolo bocca dx
                    }
                    
                    scale_factor = -1.5 
                    depth_factor = 1.5
                    
                    for bone_name, (lm_idx, parent_idx) in bone_map.items():
                        bone = arm_obj.pose.bones.get(bone_name)
                        if bone:
                            lm = landmarks[lm_idx]
                            
                            if parent_idx is None:
                                pos_x = (lm.x - 0.5) * scale_factor
                                pos_y = (lm.y - 0.5) * scale_factor
                                pos_z = lm.z * depth_factor
                            else:
                                parent_lm = landmarks[parent_idx]
                                pos_x = (lm.x - parent_lm.x) * scale_factor
                                pos_y = (lm.y - parent_lm.y) * scale_factor
                                pos_z = (lm.z - parent_lm.z) * depth_factor
                                
                            bone.location = (pos_x, pos_y, pos_z)

        # fa eseguire anche gli altri eventi per ad es ruotare la visuale di Blender mentre la webcam è accesa
        return {'PASS_THROUGH'}

    def execute(self, context):
        self._tracker = FaceTracker()
        if not self._tracker.start():
            self.report({'ERROR'}, "Impossibile avviare la webcam.")
            return {'CANCELLED'}
        
        #timer per non bloccare blender
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.03, window=context.window)
        wm.modal_handler_add(self)
        
        self.report({'INFO'}, "Motion Capture Avviata! Premi ESC per fermarla.")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        if self._tracker:
            self._tracker.stop()
        self.report({'INFO'}, "Motion Capture Fermata.")