import bpy
import os
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from mathutils import Vector
from ..core import head_measure, solver
from ..core.config import ROTATION_BONES, FACE_MAPPING, BODY_BONES, NECK_HEAD_SHAPE
from ..core.rig import BASE_RIG_NAME, create_bones, find_rig
from ..core.weights import bind_by_islands, clean_loose_geometry, limit_body_weights

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
    """Collega la mesh selezionata all'armatura FaceMocap con Pesi Automatici.

    Ri-eseguibile: i pesi automatici vengono calcolati UNA VOLTA SOLA, sulle
    posizioni che le ossa hanno al momento del click. Spostare le ossa in Edit
    Mode dopo il collegamento non li ricalcola: bisogna ri-collegare. Per questo
    l'operatore riparte ogni volta da zero invece di accumulare modificatori.
    """
    bl_idname = "facemocap.bind_model"
    bl_label = "Collega all'Armatura"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        arm_obj = find_rig()
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
            
        avvisi = _reset_binding(mesh_obj, arm_obj)
        avvisi += _check_levers(arm_obj)

        n_sciolti = clean_loose_geometry(mesh_obj)
        if n_sciolti:
            avvisi.append("rimossi %d vertici sciolti" % n_sciolti)

        avvisi += bind_by_islands(mesh_obj, arm_obj, context)
        avvisi += limit_body_weights(mesh_obj, arm_obj)

        # parent_set aggiunge un modificatore anche quando la mesh e' gia'
        # imparentata: senza questo, un secondo click deforma due volte.
        avvisi += _dedup_armature_modifiers(mesh_obj, arm_obj)

        vuoti = _empty_deform_groups(mesh_obj, arm_obj)
        if vuoti:
            # Il bone heat non ha assegnato nulla a queste ossa: di solito sono
            # troppo vicine a una vicina piu' grande, o fuori dalla superficie.
            avvisi.append("ossa senza peso: %s" % ", ".join(vuoti))

        bpy.ops.object.select_all(action='DESELECT')
        mesh_obj.select_set(True)
        context.view_layer.objects.active = mesh_obj

        if avvisi:
            self.report({'WARNING'}, "%s collegato - %s" % (
                mesh_obj.name, " | ".join(avvisi)))
        else:
            self.report({'INFO'}, f"Modello {mesh_obj.name} collegato all'armatura!")
        return {'FINISHED'}


def _reset_binding(mesh_obj, arm_obj):
    """Riporta la mesh allo stato pre-collegamento.

    Senza questo, ogni click impila un modificatore Armature in piu' e i vertex
    group vecchi sopravvivono: i pesi calcolati su una posizione precedente
    delle ossa restano mescolati a quelli nuovi.
    """
    avvisi = []

    n_mod = 0
    for mod in list(mesh_obj.modifiers):
        if mod.type == 'ARMATURE':
            mesh_obj.modifiers.remove(mod)
            n_mod += 1
    if n_mod > 1:
        avvisi.append("rimossi %d modificatori Armature accumulati" % n_mod)

    # Solo i gruppi che corrispondono a un osso del rig: quelli creati a mano
    # dall'utente per altri scopi non vanno toccati.
    nomi_ossa = {b.name for b in arm_obj.data.bones}
    for vg in list(mesh_obj.vertex_groups):
        if vg.name in nomi_ossa:
            mesh_obj.vertex_groups.remove(vg)

    if mesh_obj.parent is arm_obj:
        matrice = mesh_obj.matrix_world.copy()
        mesh_obj.parent = None
        mesh_obj.matrix_world = matrice

    return avvisi


def _dedup_armature_modifiers(mesh_obj, arm_obj):
    """Lascia un solo modificatore Armature, legato al rig."""
    armature = [m for m in mesh_obj.modifiers if m.type == 'ARMATURE']
    if len(armature) <= 1:
        for mod in armature:
            mod.object = arm_obj
        return []

    tenuto = None
    for mod in armature:
        if mod.object is arm_obj and tenuto is None:
            tenuto = mod
        else:
            mesh_obj.modifiers.remove(mod)
    if tenuto is None:
        tenuto = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
    tenuto.object = arm_obj
    return ["rimossi %d modificatori Armature doppi" % (len(armature) - 1)]


def _check_levers(arm_obj):
    """Verifica che le ossa a leva abbiano la coda rivolta verso il basso.

    core/solver.py scarta silenziosamente una leva con la coda in su e ripiega
    sulla traslazione: meglio dirlo qui, quando si puo' ancora correggere.
    """
    avvisi = []
    for nome in ROTATION_BONES:
        osso = arm_obj.data.bones.get(nome)
        if osso is None:
            continue
        if not solver.is_valid_lever(osso.tail_local - osso.head_local):
            avvisi.append(
                "%s non e' una leva valida (coda in su): mettine la TESTA sul "
                "perno all'altezza delle orecchie e la CODA sul mento, "
                "altrimenti la mandibola non ruota" % nome
            )
    return avvisi


def _empty_deform_groups(mesh_obj, arm_obj):
    """Nomi delle ossa deformanti rimaste senza alcun peso."""
    con_peso = set()
    for vert in mesh_obj.data.vertices:
        for g in vert.groups:
            if g.weight > 0.01:
                con_peso.add(g.group)

    vuoti = []
    for osso in arm_obj.data.bones:
        if not osso.use_deform:
            continue
        vg = mesh_obj.vertex_groups.get(osso.name)
        if vg is None or vg.index not in con_peso:
            vuoti.append(osso.name)
    return vuoti


# OPERATORE PER L'ARMATURA ADATTIVA
class FACEMOCAP_OT_create_adaptive_armature(bpy.types.Operator):
    """Genera l'armatura proporzionata al modello selezionato. Controlla le ossa in Edit Mode se il viso ha proporzioni diverse dal modello di riferimento."""
    bl_idname = "facemocap.create_adaptive_armature"
    bl_label = "Genera Armatura su Modello"

    def execute(self, context):
        mesh_obj = context.active_object
        if not mesh_obj or mesh_obj.type != 'MESH':
            self.report({'ERROR'}, "Seleziona prima il tuo modello 3D!")
            return {'CANCELLED'}

        # Misure in coordinate mondo: con un modello importato ruotato (Y-up)
        # mesh_obj.dimensions scambia altezza e profondita'. Se c'e' il collo
        # il template si adatta alla testa misurata, non al bbox del busto.
        misura = head_measure.misura_modello(mesh_obj, context.scene.objects)
        origine = misura.mappa.to_world((0.0, 0.0, 0.0))

        old_arm = find_rig()
        if old_arm:
            bpy.data.objects.remove(old_arm, do_unlink=True)

        arm_data = bpy.data.armatures.new(name="FaceMocap_Rig_Data")
        arm_obj = bpy.data.objects.new(name=BASE_RIG_NAME, object_data=arm_data)
        context.collection.objects.link(arm_obj)
        
        arm_obj.location = origine

        context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode='EDIT')

        # Le posizioni di FACE_MAPPING sono nelle coordinate del template: qui
        # diventano le misure di QUESTO modello, relative all'origine del rig.
        def adapt(pos):
            return misura.mappa.to_world(pos) - origine

        create_bones(
            arm_data,
            adapt=adapt,
            tail_length=lambda name: misura.altezza * 0.1,
        )
        if misura.collo_base is not None:
            _aggiungi_collo(arm_data, misura, adapt, origine)

        bpy.ops.object.mode_set(mode='OBJECT')
        arm_obj.show_in_front = True

        # Ancora = dove sta il landmark dell'osso. Per Head e Jaw non coincide
        # con la testa (base del collo, perno della mandibola) e il solver la
        # usa per misurare la scala del rig.
        for name, data in FACE_MAPPING.items():
            bone = arm_data.bones.get(name)
            if bone is not None:
                bone["fm_anchor"] = list(adapt(data.position))
        
        bpy.ops.object.select_all(action='DESELECT')
        arm_obj.select_set(True)
        context.view_layer.objects.active = arm_obj

        print("\n".join(["FaceMocap - armatura generata su %s" % mesh_obj.name]
                        + ["  " + r for r in misura.righe()]), flush=True)

        if misura.modo == "testa":
            testo = ("Armatura generata sulla testa (collo riconosciuto, ossa %s). "
                     % ", ".join(n for n in BODY_BONES if n in arm_data.bones))
        else:
            testo = "Armatura generata sul bbox del modello. "
        testo += "Controlla le ossa, poi premi Collega Manualmente. Misure in console."
        self.report({'WARNING'} if misura.note and misura.modo == "testa" else {'INFO'}, testo)
        return {'FINISHED'}


def _aggiungi_collo(arm_data, misura, adapt, origine):
    """Neck dalla base del collo alla base del cranio, Head da li' in su.

    Head ruota attorno alla base del cranio invece che attorno al fondo del
    bbox, cioe' le spalle. La rotazione si divide lungo la catena: Chest ne
    prende poca e porta con se' l'inizio delle spalle, Neck piega il collo,
    Head fa il resto (NECK_ROT_SHARE, CHEST_ROT_SHARE).
    L'armatura dev'essere in Edit Mode.
    """
    edit_bones = arm_data.edit_bones
    head = edit_bones["Head"]
    testa_head = adapt(NECK_HEAD_SHAPE[0])
    collo_base = Vector(misura.collo_base) - origine
    if testa_head.z <= collo_base.z:
        misura.note.append("base del cranio sotto la base del collo: Neck non creato")
        return

    head.head = testa_head
    head.tail = adapt(NECK_HEAD_SHAPE[1])

    neck = edit_bones.new("Neck")
    neck.head = collo_base
    neck.tail = testa_head
    head.parent = neck
    head.use_connect = False

    if misura.torace_base is not None:
        chest = edit_bones.new("Chest")
        chest.head = Vector(misura.torace_base) - origine
        chest.tail = collo_base
        neck.parent = chest