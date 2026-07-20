import bpy

class FACEMOCAP_PT_main_panel(bpy.types.Panel):
    """Crea un Pannello nella barra laterale (N) della Vista 3D"""
    bl_label = "FaceMocap"
    bl_idname = "FACEMOCAP_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'FaceMocap'

    def draw(self, context):
        layout = self.layout

        layout.label(text="Sistema pronto", icon='OUTLINER_OB_ARMATURE')
        
        layout.separator()
        
        # bottone che chiama operators.py
        layout.operator("facemocap.create_armature", text="Genera Armatura Facciale", icon='BONE_DATA')

        layout.separator()
        
        # Bottone per accendere la webcam e avviare il tracking
        layout.operator("facemocap.start_capture", text="Avvia Motion Capture", icon='PLAY')