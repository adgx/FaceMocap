from typing import Any

import bpy

from bpy.types import(
    Context,
    Panel,
    UILayout,
    UIList
)
from ..core import properties 

class FACEMOCAP_UL_mapping(UIList):
    bl_idname = "FACEMOCAP_UL_mapping"

    def draw_item(self, context: Context | None, layout: UILayout, data: None | Any, item: None | Any, icon: int | None, active_data: Any, active_property: str | None, index: int | None, flt_flag: int | None) -> None:
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=item.role)
        row.label(text=item.target_bone)
        row.label(text=item.source_bones)
        row.prop(item, "mode", text="")
        row.prop(item, "gain", text="")

class FACEMOCAP_PT_main_panel(Panel):
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
        settings = (context.scene.facemocap)

        # Importazione Modello
        box_model = layout.box()
        box_model.label(text="3D Mesh", icon='MESH_MONKEY')
        box_model.operator("facemocap.import_custom_model", text="Importa Modello", icon='IMPORT')

        # Setup dell'Armatura
        box_setup = layout.box()
        box_setup.label(text="Setup Armature", icon='OUTLINER_OB_ARMATURE')

        # Generatore Armatura Standard
        box_setup.operator("facemocap.create_armature", text="Generate Base Armature", icon='BONE_DATA')
        # Generatore Armatura adattata al modello
        box_setup.operator("facemocap.create_adaptive_armature", text="Generate Armature Base On Mesh", icon='ARMATURE_DATA')
        # Operatore manuale per collegare i pesi
        box_setup.operator("facemocap.bind_model", text="Link Manually", icon='LINKED')

        # Setup source rig and target rig
        box_advance_setup = layout.box()
        box_advance_setup.label(text="Advance Setup", icon="OUTLINER_OB_ARMATURE")
        box_advance_setup.prop(settings, "source_rig_name", text="Source")
        box_advance_setup.prop(settings, "target_rig_name", text="Target")
        row = box_advance_setup.row(align=True)
        row.operator("facemocap.initialize", icon="FILE_REFRESH")
        row.operator("facemocap.validate", icon="CHECKMARK")
        # Generatore source rig
        box_advance_setup.operator("facemocap.create_advance_armature", text="Generate Source Rig", icon='BONE_DATA')
        #Mapping
        box_mapping = layout.box()
        box_mapping.label(text="Target Mapping")
        box_mapping.template_list("FACEMOCAP_UL_mapping", 
                                  "",
                                  settings,
                                  "mappings",
                                  settings,
                                  "mapping_index",
                                  rows=0)
        index = (settings.mapping_index)

        if 0 <= index < len(settings.mappings):
            item = (settings.mappings[index])
            detail = box_mapping.box()
            detail.label(text="Mapping")
            row = detail.row()
            row.enabled = False
            row.prop(item, "role")
            detail.prop(item, "target_bone")
            detail.prop(item, "source_bones")

        
        # Motion Capture
        box_mocap = layout.box()
        box_mocap.label(text="Campture", icon='ANIM')
        box_mocap.prop(settings, "camera_id")
        box_mocap.prop(settings, "mirror_x")
        box_mocap.prop(settings, "smoothing")

        box_mocap.prop(settings, "show_preview")

        box_mocap.operator("facemocap.start_capture", text="Start Motion Capture", icon='PLAY')
        box_mocap.operator("facemocap.reset_pose", text="Reset Pose", icon='LOOP_BACK')
        box_mocap.label(text="ESC = stop | C = recalibration")
