import bpy


class FACEMOCAP_PT_main_panel(bpy.types.Panel):
    """Crea un Pannello nella barra laterale (N) della Vista 3D
       Pannel on View 3D
    """
    bl_label = "FaceMocap"
    bl_idname = "FACEMOCAP_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'FaceMocap'

    def draw(self, context):
        layout = self.layout

        # Importazione Modello
        box_model = layout.box()
        box_model.label(text="1. 3D Mesh", icon='MESH_MONKEY')
        box_model.operator("facemocap.import_custom_model", text="Importa Modello", icon='IMPORT')

        # Setup dell'Armatura
        box_setup = layout.box()
        box_setup.label(text="2. Setup Armature", icon='OUTLINER_OB_ARMATURE')

        # Generatore Armatura Standard
        box_setup.operator("facemocap.create_armature", text="Generate Base Armature", icon='BONE_DATA')
        # Generatore Armatura Advance
        box_setup.operator("facemocap.create_advance_armature", text="Generate Advance Armature", icon='BONE_DATA')

        # Generatore Armatura adattata al modello
        box_setup.operator("facemocap.create_adaptive_armature", text="Generate Armature Base On Mesh", icon='ARMATURE_DATA')

        # Operatore manuale per collegare i pesi
        box_setup.operator("facemocap.bind_model", text="Link Manually", icon='LINKED')

        # Motion Capture
        box_mocap = layout.box()
        box_mocap.label(text="3. Animazione", icon='ANIM')
        settings = context.scene.facemocap
        box_mocap.prop(settings, "mirror_x")
        box_mocap.operator("facemocap.start_capture", text="Start Motion Capture", icon='PLAY')
        box_mocap.operator("facemocap.reset_pose", text="Reset Pose", icon='LOOP_BACK')
        box_mocap.label(text="ESC = stop | C = recalibration")
