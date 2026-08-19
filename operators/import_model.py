import bpy
import os
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from mathutils import Vector
from ..core.config import FACE_MAPPING

# OPERATORE PER IMPORTARE IL MODELLO
class FACEMOCAP_OT_import_custom_model(bpy.types.Operator, ImportHelper):
    """Importa un modello 3D personalizzato (.obj, .fbx, .glb, .blend)"""
    bl_idname = "facemocap.import_custom_model"
    bl_label = "Importa Modello"

    filter_glob: StringProperty(
        default="*.obj;*.fbx;*.glb;*.gltf;*.blend",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        ext = os.path.splitext(self.filepath)[1].lower()
        try:
            if ext == '.obj':
                bpy.ops.wm.obj_import(filepath=self.filepath)
            elif ext == '.fbx':
                bpy.ops.import_scene.fbx(filepath=self.filepath)
            elif ext in {'.glb', '.gltf'}:
                bpy.ops.import_scene.gltf(filepath=self.filepath)
            elif ext == '.blend':
                with bpy.data.libraries.load(self.filepath, link=False) as (data_from, data_to):
                    data_to.objects = [name for name in data_from.objects]

                for obj in data_to.objects:
                    if obj is not None:
                        context.collection.objects.link(obj)
                        obj.select_set(True)
                        context.view_layer.objects.active = obj
                        
            else:
                self.report({'ERROR'}, f"Formato {ext} non supportato.")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Errore durante l'importazione: {e}")
            return {'CANCELLED'}
            
        self.report({'INFO'}, "Modello importato con successo!")
        return {'FINISHED'}


# OPERATORE PER COLLEGARE IL MODELLO ALL'ARMATURA
class FACEMOCAP_OT_bind_model(bpy.types.Operator):
    """Collega la mesh selezionata all'armatura FaceMocap con Pesi Automatici"""
    bl_idname = "facemocap.bind_model"
    bl_label = "Collega all'Armatura"

    def execute(self, context):
        arm_obj = bpy.data.objects.get("FaceMocap_Rig")
        if not arm_obj:
            self.report({'ERROR'}, "Armatura FaceMocap non trovata.")
            return {'CANCELLED'}
            
        mesh_obj = None
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                mesh_obj = obj
                break
        
        if not mesh_obj and context.active_object and context.active_object.type == 'MESH':
            mesh_obj = context.active_object
            
        if not mesh_obj:
            self.report({'WARNING'}, "Seleziona il tuo modello 3D (Mesh) prima di cliccare!")
            return {'CANCELLED'}
            
        bpy.ops.object.select_all(action='DESELECT')
        
        mesh_obj.select_set(True)
        arm_obj.select_set(True)
        context.view_layer.objects.active = arm_obj
        
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        
        bpy.ops.object.select_all(action='DESELECT')
        mesh_obj.select_set(True)
        context.view_layer.objects.active = mesh_obj
        
        self.report({'INFO'}, f"Modello {mesh_obj.name} collegato all'armatura!")
        return {'FINISHED'}


# OPERATORE PER L'ARMATURA ADATTIVA
class FACEMOCAP_OT_create_adaptive_armature(bpy.types.Operator):
    """Genera un'armatura proporzionata. RICHIEDE POSIZIONAMENTO MANUALE IN EDIT MODE prima del collegamento."""
    bl_idname = "facemocap.create_adaptive_armature"
    bl_label = "Genera Armatura su Modello"

    def execute(self, context):
        mesh_obj = context.active_object
        if not mesh_obj or mesh_obj.type != 'MESH':
            self.report({'ERROR'}, "Seleziona prima il tuo modello 3D!")
            return {'CANCELLED'}

        dims = mesh_obj.dimensions
        
        local_bbox_center = sum((Vector(b) for b in mesh_obj.bound_box), Vector()) / 8
        world_center = mesh_obj.matrix_world @ local_bbox_center
        
        world_center.z += dims.z * 0.15 

        old_arm = bpy.data.objects.get("FaceMocap_Rig")
        if old_arm:
            bpy.data.objects.remove(old_arm, do_unlink=True)

        arm_data = bpy.data.armatures.new(name="FaceMocap_Rig_Data")
        arm_obj = bpy.data.objects.new(name="FaceMocap_Rig", object_data=arm_data)
        context.collection.objects.link(arm_obj)
        
        arm_obj.location = world_center
        
        context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = arm_data.edit_bones
        
        for bone_name, data in FACE_MAPPING.items():
            base_pos = data[3] 
            
            adapted_x = base_pos[0] * dims.x * 0.5
            adapted_y = base_pos[1] * dims.y * 0.5
            adapted_z = base_pos[2] * dims.z * 0.5
            
            b = edit_bones.new(bone_name)
            b.head = (adapted_x, adapted_y, adapted_z)
            b.tail = (adapted_x, adapted_y, adapted_z + (dims.z * 0.1))

        for bone_name, data in FACE_MAPPING.items():
            parent_bone_name = data[2]
            if parent_bone_name:
                edit_bones[bone_name].parent = edit_bones[parent_bone_name]
        
        bpy.ops.object.mode_set(mode='OBJECT')
        arm_obj.show_in_front = True
        
        bpy.ops.object.select_all(action='DESELECT')
        arm_obj.select_set(True)
        context.view_layer.objects.active = arm_obj
        
        self.report({'INFO'}, "Armatura generata! ORA ENTRA IN EDIT MODE E POSIZIONA LE OSSA.")
        return {'FINISHED'}