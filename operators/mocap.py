from typing import Literal, NamedTuple

import bpy
from bpy.types import Context
from mathutils import Matrix, Quaternion, Vector
import math
import time
import traceback
from ..core.one_euro_filter import OneEuroFilter, OneEuroFilterQuaternion

from ..core import solver
from ..core import properties
from ..core import config
from ..core import rig
from ..core.retarget import RetargetSolver
from ..core.config import MappingRuntime, MotionMode, LANDMARKS_MAP, FACE_MAPPING, LANDMARKERS_FACE_MAPPING, LM_FOREHEAD, LM_NASION, LM_SIDE_L, LM_SIDE_R
from ..core.rig import find_rig, reset_rig_pose, LANDMARKS_RIG_NAME, BASE_RIG_NAME
from ..core.webcam_core import FaceTracker
from .diagnostics import stampa_tabella_scale

TRACKED_INDICES = sorted(
    {data.landmark for data in FACE_MAPPING.values()}
    | {data.parent_landmark for data in FACE_MAPPING.values()
       if data.parent_landmark is not None}
    | {LM_SIDE_R, LM_SIDE_L, LM_FOREHEAD, LM_NASION}
)

ADVANCE_TRACKED_INDICES = sorted(
    {data.landmark for data in LANDMARKERS_FACE_MAPPING.values()}
    | {data.parent_landmark for data in LANDMARKERS_FACE_MAPPING.values()
       if data.parent_landmark is not None}
    | {LM_SIDE_R, LM_SIDE_L, LM_FOREHEAD, LM_NASION}
)

def _gain_gruppo(bone_name):
    """Moltiplicatore d'ampiezza del gruppo a cui l'osso appartiene."""
    if bone_name == "Jaw":
        return config.JAW_GAIN
    if bone_name.startswith("Mouth_Corner"):
        return config.MOUTH_CORNER_GAIN
    if bone_name.startswith(("Lip_", "Mouth_")):
        return config.MOUTH_GAIN
    if bone_name.startswith(("Eye_", "Eyelid_")):
        return config.EYE_GAIN
    if bone_name.startswith("Brow_"):
        return config.BROW_GAIN
    return 1.0


class _Voce(NamedTuple):
    osso: str
    #Mediapipe relationship
    landmark: int
    genitore: int | None
    #Mirrored mediapipe relationship 
    landmark_speculare: int
    genitore_speculare: int
    gain: float               # gain per-osso gia' moltiplicato per quello di gruppo
    rotazione: bool           # osso a leva (mandibola) invece che in traslazione
    #type of motion
    motion_mode: MotionMode

#to review in way to adapt it for the advance_rig
def _piano_ossa() -> list[_Voce]:
    voci = []

    for nome, data in FACE_MAPPING.items():
        speculare = FACE_MAPPING[solver.mirrored_bone_name(nome)]
        voci.append(_Voce(
            osso=nome,
            landmark=data.landmark,
            genitore=data.parent_landmark,
            landmark_speculare=speculare.landmark,
            genitore_speculare=speculare.parent_landmark,
            gain=data.gain * _gain_gruppo(nome),
            rotazione=nome in config.ROTATION_BONES,
            motion_mode= data.motion_mode
        ))
    return voci

PIANO_OSSA = _piano_ossa()


def _rotazione_catena(pose_bone):
    """Rotazione di posa, in assi armatura, dell'osso e di tutti i suoi genitori."""
    rot = Matrix.Identity(3)
    while pose_bone is not None:
        rot = solver.bone_pose_rotation(pose_bone) @ rot
        pose_bone = pose_bone.parent
    return rot

####################################################
#               Operators Classes                  #
####################################################
class FACEMOCAP_OT_initialize(bpy.types.Operator):
    """Loads the default mapping"""
    bl_idname = "facemocap.initialize"
    bl_label = "Load Default Mapping"

    def execute(self, context: Context) -> set[Literal['RUNNING_MODAL'] | Literal['CANCELLED'] | Literal['FINISHED'] | Literal['PASS_THROUGH'] | Literal['INTERFACE']]:
        properties.populate_default_mapping(context.scene.facemocap)
        self.report({"INFO"}, "Default mapping loaded")

        return {"FINISHED"}

class FACEMOCAP_OT_reset_pose(bpy.types.Operator):
    """Riporta l'armatura alla rest pose
       Reset pose to the default
    """
    bl_idname = "facemocap.reset_pose"
    bl_label = "Reset pose"
    bl_description = "Reset the pose to the default"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context) -> set[Literal['RUNNING_MODAL'] | Literal['CANCELLED'] | Literal['FINISHED'] | Literal['PASS_THROUGH'] | Literal['INTERFACE']]:
        settings = (context.scene.facemocap)
        #search the base rig
        rig = find_rig(context)
        if not rig:
            #search source rig
            source_rig = find_rig(context, settings.source_rig_name)
            if not source_rig:
                self.report({'ERROR'}, "Base FaceMocap Armature not found.")
                return {'CANCELLED'}
            reset_rig_pose(source_rig)
            target_rig = find_rig(context, settings.target_rig_name)
            if not target_rig:
                self.report({'ERROR'}, "Armatura FaceMocap not found.")
                return {'FINISHED'}
            reset_rig_pose(target_rig)        
            return {'FINISHED'}

        reset_rig_pose(rig)
        return {'FINISHED'}

class FACEMOCAP_OT_validate(bpy.types.Operator):
    """Checks whether the mapping is valid for motion capture and applies it"""
    bl_idname = "facemocap.validate"
    bl_label = "validate Mapping"

    def execute(self, context) -> set[Literal['RUNNING_MODAL'] | Literal['CANCELLED'] | Literal['FINISHED'] | Literal['PASS_THROUGH'] | Literal['INTERFACE']]:
        """Check whether the target rig has all target bones specified in the mapping"""
        settings = (context.scene.facemocap)
        target = rig.find_rig(context, settings.target_rig_name)

        if target is None:
            self.report({"ERROR"}, "Target rig not found")
            return {"CANCELLED"}

        missing = []

        for item in settings.mappings:
            if not item.enabled:
                continue
            if not item.target_bone:
                continue
            if(target.pose.bones.get(item.target_bone) is None):
                missing.append(item.target_bone)

        if missing:
            self.report({"WARNING"}, "Missing bones: " + ",".join(missing))
        else:
            self.report({"INFO"}, "Target mapping is valid")

        return {"FINISHED"}

class FACEMOCAP_OT_start_capture(bpy.types.Operator):
    """Avvia la motion capture facciale. ESC per fermare, C per ricalibrare
       Start the facial motion capture. Esc to stop, and C for recalibrating 
    """
    bl_idname = "facemocap.start_capture"
    bl_label = "Start Motion Capture"
    bl_description = "Creation of the armatrue for the motion capture"

    _timer = None
    _tracker = None
    _area = None
    _rig = None
    _base_mocap = False
    _target_rig = None
    _track_idx = TRACKED_INDICES
    retarget = RetargetSolver()

    def apply_target(self, target_pose):
        """Applica al target rig le pose calcolate dal RetargetSolver (in assi armatura)."""
        if self._target_rig is None:
            return

        mapping_by_role = {mapping.role: mapping for mapping in self.mappings}

        for role, (mode, value) in target_pose.items():
            mapping = (mapping_by_role.get(role))

            if mapping is None:
                continue

            pose_bone = (self._target_rig.pose.bones.get(mapping.target_bone))

            if pose_bone is None:
                continue

            if mode == "TRANSLATION":
                rig.apply_translation(pose_bone, value)
            elif mode == "ROTATION":
                rig.apply_rotation(pose_bone, solver.rotation_to_bone_space(pose_bone, value.to_matrix()))

        return True

    def _filter(self, key, filter_cls, settings):
        """Filtro 1Euro associato alla chiave, con i parametri correnti della UI."""
        flt = self._filters.get(key)
        if flt is None:
            flt = self._filters[key] = filter_cls()
        flt.min_cutoff = settings.min_cutoff
        flt.beta = settings.beta
        return flt

    def _apply_pose(self, context: bpy.types.Context, source_pose: solver.SourcePose, t_now):
        settings = context.scene.facemocap

        # Delta rispetto alla posa neutra, ancora in sist. di rif. testa-locale.
        deltas = {
            idx: vec - self.retarget._neutral[idx]
            for idx, vec in source_pose.local.items()
            if idx in self.retarget._neutral
        }

        # Prima delle traslazioni: Head e' figlio di Neck, e la sua traslazione
        # va tolta dalla rotazione di Neck di QUESTO frame, non del precedente.
        self._apply_head_rotation(context, source_pose, t_now)

        amounts = None
        if source_pose.blendshapes:
            amounts = self._blendshape_amounts(settings, source_pose.blendshapes, t_now)
        self._last_amounts = amounts

        for voce in PIANO_OSSA:
            pose_bone = self._rig.pose.bones.get(voce.osso)
            if not pose_bone:
                continue

            # Palpebre dai blendshape: valori gia' normalizzati 0..1
            # e filtrati, quindi la chiusura completa arriva sempre sul rig.
            if amounts is not None and self._apply_blendshape_bone(pose_bone, voce.osso, amounts, settings):
                continue

            if settings.mirror_x:
                lm_idx, parent_idx = voce.landmark_speculare, voce.genitore_speculare
            else:
                lm_idx, parent_idx = voce.landmark, voce.genitore

            # factor: unita' armatura per larghezza viso, gain inclusi. Serve al
            # filtro per misurare la velocita' indipendentemente da rig e gain.
            if parent_idx is None:
                factor = self.retarget._unit_scale * config.HEAD_GAIN * voce.gain
                target = self._solve_head_translation(settings, source_pose) * voce.gain
            else:
                if lm_idx not in deltas or parent_idx not in deltas:
                    continue
                relative = deltas[lm_idx] - deltas[parent_idx]
                scale_b = self.retarget._bone_scales.get(voce.osso, self.retarget._unit_scale)
                factor = scale_b * config.AMPLITUDE * voce.gain
                target = solver.head_local_to_blender(relative, settings.mirror_x) * factor

                if voce.rotazione:
                    if self._apply_lever_rotation(pose_bone, voce.osso, target, t_now):
                        continue
                    self._warn_bad_lever(voce.osso)

            flt = self._filter(voce.osso, OneEuroFilter, settings)
            flt.velocity_scale = factor
            smoothed = flt.filter(target, t_now)
            # Lo spostamento e' nel frame della testa, ma l'osso si muove nel
            # frame del genitore: se il genitore e' la mandibola gia' ruotata,
            # quella rotazione va tolta, altrimenti le labbra ruotano due volte.
            # Head sotto Neck e Chest ruotati: la sua traslazione e' uno
            # spostamento nello spazio, e va tolta la rotazione dell'intera
            # catena del corpo.
            parent = pose_bone.parent
            if parent is not None and parent.name == "Jaw":
                smoothed = solver.bone_pose_rotation(parent).inverted() @ smoothed
            elif parent is not None and parent.name in config.BODY_BONES:
                smoothed = _rotazione_catena(parent).inverted() @ smoothed
            pose_bone.location = solver.traslation_to_bone_space(pose_bone, smoothed)

    def _blendshape_amounts(self, settings, scores, t_now):
        """Blendshape usati dal rig, 0 (neutro) .. 1 (completo), filtrati.

        Il filtro lavora sul valore normalizzato: un battito di ciglia vale
        ~20 unita'/s e il cutoff dinamico sale abbastanza da non tagliarlo.
        """
        out = {}
        for name, full in config.BLENDSHAPE_FULL.items():
            raw = solver.blendshape_amount(scores, self.retarget._neutral_blendshapes, name, full)
            flt = self._filter("bs:" + name, OneEuroFilter, settings)
            out[name] = flt.filter(Vector((raw, 0.0, 0.0)), t_now).x
        return out

    def _log_debug(self, context, source_pose, t_now):
        """Una riga al secondo in console: angoli della testa misurati e
        applicati, traslazione, blendshape di occhi e bocca."""
        if t_now - getattr(self, "_last_log", -1.0) < 1.0:
            return
        self._last_log = t_now

        def gradi(rot):
            return "(%+6.1f %+6.1f %+6.1f)" % tuple(math.degrees(a) for a in rot.to_euler())

        settings = context.scene.facemocap
        da_landmark = solver.head_rotation_matrix(self.retarget._neutral_rot, source_pose.head_rotation)
        righe = ["FaceMocap LOG t=%.1f  rotazione testa in gradi (X annuire, Y inclinare, Z girare)" % t_now,
                 "  landmark  %s" % gradi(da_landmark)]
        if source_pose.pose_rotation is not None and self.retarget._neutral_pose_rot is not None:
            righe.append("  matrice   %s" % gradi(self.retarget.head_rotation(source_pose)))
        else:
            righe.append("  matrice   non disponibile")

        head = self._rig.pose.bones.get("Head")
        if head is not None:
            applicata = head.bone.matrix_local.to_3x3() @ head.rotation_quaternion.to_matrix() \
                @ head.bone.matrix_local.to_3x3().inverted()
            righe.append("  applicata %s  (angolo totale %.1f)  location %s  traslazione %s fw"
                         % (gradi(applicata), math.degrees(head.rotation_quaternion.angle),
                            tuple(round(v, 4) for v in head.location),
                            tuple(round(v, 3) for v in self._solve_head_translation(settings, source_pose)
                                  / (self.retarget._unit_scale * config.HEAD_GAIN))))

        righe += self._righe_prestazioni(settings)

        for nome, quota in (("Chest", config.CHEST_ROT_SHARE), ("Neck", config.NECK_ROT_SHARE)):
            osso = self._rig.pose.bones.get(nome)
            if osso is not None:
                righe.append("  %-9s angolo %.1f  (quota %.0f%% della rotazione)"
                             % (nome, math.degrees(osso.rotation_quaternion.angle), quota * 100))

        # Bocca: angolo della mandibola, spostamento reale (MediaPipe, in
        # larghezze di viso, assi armatura) e spostamento applicato alle ossa.
        jaw = self._rig.pose.bones.get("Jaw")
        if jaw is not None:
            righe.append("  Jaw angolo applicato %.1f gradi" % math.degrees(jaw.rotation_quaternion.angle))
        for idx, etichetta in ((152, "mento (152)"), (17, "labbro inf (17)"), (0, "labbro sup (0)"), (291, "angolo bocca (291)")):
            if idx in source_pose.local and idx in self.retarget._neutral:
                delta = solver.head_local_to_blender(source_pose.local[idx] - self.retarget._neutral[idx])
                righe.append("  reale %-19s %s fw" % (etichetta, tuple(round(v, 3) for v in delta)))
        for nome in ("Lip_Upper", "Lip_Lower", "Mouth_Corner.L"):
            pb = self._rig.pose.bones.get(nome)
            if pb is not None:
                spost = pb.bone.matrix_local.to_3x3() @ pb.location
                righe.append("  osso %-15s spostamento %s mm" % (nome, tuple(round(v * 1000, 1) for v in spost)))

        scores = source_pose.blendshapes or {}
        neutral = self.retarget._neutral_blendshapes
        amounts = getattr(self, "_last_amounts", None) or {}
        for name in ("eyeBlinkLeft", "eyeBlinkRight", "jawOpen", "eyeWideLeft", "eyeSquintLeft"):
            righe.append("  %-14s grezzo %.3f  neutro %.3f  normalizzato %.2f"
                         % (name, scores.get(name, float("nan")), neutral.get(name, float("nan")),
                            amounts.get(name, float("nan"))))
        print("\n".join(righe), flush=True)

    @staticmethod
    def _perf_vuote():
        return {"ultimo": None, "tick": 0, "intervallo_s": 0.0, "lavoro_s": 0.0}

    def _righe_prestazioni(self, settings):
        """Dove si perde tempo: Blender, webcam, MediaPipe o filtro.

        Letti insieme:
          - tick/s molto sotto ~30 o intervallo lungo: Blender e' lento a
            ridisegnare/deformare, il rig si aggiorna di rado;
          - frame catturati sotto ~30: la webcam stessa e' lenta (luce scarsa,
            esposizione automatica);
          - eta risultato alta: MediaPipe e' lento;
          - tutto nella norma: il ritardo e' del filtro (Cutoff/Beta).
        """
        perf = self._perf
        webcam = self._tracker.pop_stats()
        tick = perf["tick"]
        righe = ["  prestazioni (dall'ultima riga di log):"]
        if tick:
            durata = perf["intervallo_s"]
            righe.append("    tick %.1f/s   intervallo medio %.0f ms   lavoro FaceMocap %.0f ms/tick"
                         % (tick / durata if durata > 0 else 0.0,
                            durata / tick * 1000.0, perf["lavoro_s"] / tick * 1000.0))
        if webcam["letture"]:
            righe.append("    webcam %d frame catturati   tick con frame nuovo %d/%d   "
                         "risultati MediaPipe usati %d   eta risultato %.0f ms"
                         % (webcam["catturati"], webcam["nuovi"], webcam["letture"],
                            webcam["risultati"],
                            webcam["eta_ms"] / webcam["risultati"] if webcam["risultati"] else 0.0))
        righe.append("    filtro: Cutoff %.2f Hz  Beta %.2f" % (settings.min_cutoff, settings.beta))
        self._perf = self._perf_vuote()
        self._perf["ultimo"] = perf["ultimo"]
        return righe

    @staticmethod
    def _blendshape_side(bone_name, settings):
        """Suffisso del blendshape ("Left"/"Right") che pilota l'osso."""
        left = bone_name.endswith(".L")
        if settings.mirror_x:
            left = not left
        if config.BLENDSHAPE_SWAP_LR:
            left = not left
        return "Left" if left else "Right"

    def _apply_blendshape_bone(self, pose_bone, bone_name, amounts, settings) -> bool:
        """Pilota le palpebre dai blendshape. False se l'osso non e' gestito.

        La mandibola resta sui landmark: le labbra e gli angoli della bocca si
        muovono rispetto al mento reale, quindi Jaw deve ruotare quanto la
        mandibola vera, non di un angolo fisso.
        """
        if bone_name.startswith(("Eyelid_Up", "Eyelid_Low")):
            suffix = bone_name[-2:]
            up = self._rig.pose.bones.get("Eyelid_Up" + suffix)
            low = self._rig.pose.bones.get("Eyelid_Low" + suffix)
            if up is None or low is None:
                return False
            # apertura dell'occhio del rig, dalla palpebra superiore all'inferiore
            gap = solver.bone_anchor(low.bone) - solver.bone_anchor(up.bone)

            side = self._blendshape_side(bone_name, settings)
            blink = amounts["eyeBlink" + side]
            if bone_name.startswith("Eyelid_Up"):
                travel = blink * config.EYELID_UPPER_CLOSE - amounts["eyeWide" + side] * config.EYELID_UPPER_WIDE
            else:
                travel = -(blink * config.EYELID_LOWER_CLOSE + amounts["eyeSquint" + side] * config.EYELID_LOWER_SQUINT)
            pose_bone.location = solver.traslation_to_bone_space(pose_bone, gap * travel)
            return True

        return False


    def _warn_bad_lever(self, bone_name):
        """Avvisa una sola volta che l'osso non e' orientato come una leva."""
        if bone_name in self.retarget._warned_bones:
            return
        self.retarget._warned_bones.add(bone_name)
        self.report(
            {'WARNING'},
            "Osso '%s': la coda deve stare sul MENTO e la testa "
            "sull'articolazione vicino all'orecchio. Ora punta verso l'alto, "
            "quindi uso la traslazione. Rigenera l'armatura o riposiziona l'osso."
            % bone_name,
        )

    def _apply_lever_rotation(self, pose_bone, bone_name, tip_delta, t_now) -> bool:
        """Applica a un osso a leva (la mandibola) la rotazione corrispondente."""
        armature_rot = solver.solve_rotation_from_lever(pose_bone, tip_delta)
        if armature_rot is None:
            return False

        bone_rot = solver.rotation_to_bone_space(pose_bone, armature_rot)
        quat = bone_rot.to_quaternion()

        smoothed_quat = self._filter(bone_name, OneEuroFilterQuaternion, self.settings).filter(quat, t_now)

        if pose_bone.rotation_mode != 'QUATERNION':
            pose_bone.rotation_mode = 'QUATERNION'
        pose_bone.rotation_quaternion = smoothed_quat
        return True

    def _solve_head_translation(self, settings, source_pose):
        """Spostamento della testa nello spazio, in unita' armatura."""
        neutral_t = self.retarget._neutral_pose_t
        current_t = source_pose.pose_translation
        if neutral_t is not None and current_t is not None and abs(neutral_t.z) > 1e-6:
            # Matrice di posa: centro del viso in cm, assi camera OpenGL (y in su).
            # Ruotando la testa si sposta meno della radice del naso.
            offset = (current_t - neutral_t) / config.FACE_WIDTH_CM
            depth = (current_t.z / neutral_t.z - 1.0) * config.HEAD_DEPTH_GAIN
            vec = Vector((offset.x, depth, offset.y))
        else:
            #diviso per la scala corrente quindi il risultato e' "quante larghezze di
            # viso si e' spostata la testa", quindi indipendente dalla distanza.
            offset = (source_pose.origin - self.retarget._neutral_origin) / source_pose.scale

            depth = (self.retarget._neutral_scale / source_pose.scale - 1.0) * config.HEAD_DEPTH_GAIN

            vec = Vector((offset.x, depth, -offset.y))
        if settings.mirror_x:
            vec.x = -vec.x
        return vec * (self.retarget._unit_scale * config.HEAD_GAIN)


    def _apply_head_rotation(self, context, source_pose, t_now):
        pose_bone = self._rig.pose.bones.get("Head")
        if not pose_bone:
            return

        settings = context.scene.facemocap
        armature_rot = self.retarget.solve_head_rotation(source_pose, settings.mirror_x)
        quat = armature_rot.to_quaternion()
        if quat.w < 0.0:
            # stessa rotazione, ma con l'angolo in [0, 180]: frazionarlo
            # dall'altro emisfero girerebbe la testa dalla parte sbagliata
            quat.negate()
        axis, angle = quat.to_axis_angle()
        angle *= config.HEAD_ROT_GAIN

        # Con il collo la rotazione si divide lungo la catena Chest -> Neck ->
        # Head attorno allo stesso asse: le rotazioni commutano e la loro
        # composizione ridà l'angolo intero. Head prende quello che resta.
        resto = 1.0
        for nome, quota in (("Chest", config.CHEST_ROT_SHARE),
                            ("Neck", config.NECK_ROT_SHARE)):
            osso = self._rig.pose.bones.get(nome)
            if osso is None:
                continue
            self._set_head_rotation(osso, Quaternion(axis, angle * quota),
                                    nome + "_Rot", settings, t_now)
            resto -= quota
        self._set_head_rotation(pose_bone, Quaternion(axis, angle * resto),
                                "Head_Rot", settings, t_now)

    def _set_head_rotation(self, pose_bone, armature_quat, key, settings, t_now):
        """Rotazione in assi armatura -> quaternione di posa filtrato dell'osso."""
        bone_rot = solver.rotation_to_bone_space(pose_bone, armature_quat.to_matrix())
        smoothed_quat = self._filter(key, OneEuroFilterQuaternion, settings).filter(
            bone_rot.to_quaternion(), t_now)

        if pose_bone.rotation_mode != 'QUATERNION':
            pose_bone.rotation_mode = 'QUATERNION'
        pose_bone.rotation_quaternion = smoothed_quat

    #Handle the keywork events for the motion capture
    def modal(self, context: bpy.types.Context, event: bpy.types.Event) -> set[Literal['RUNNING_MODAL'] | Literal['CANCELLED'] | Literal['FINISHED'] | Literal['PASS_THROUGH'] | Literal['INTERFACE']]:
        """Handel the keywork events for the motion capture"""
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'C' and event.value == 'PRESS':
            self.retarget.begin_calibration(self._rig)
            if self._target_rig:
                reset_rig_pose(self._target_rig)
            self._filters = {}
            #self._set_header(context, "Ricalibrazione: mantieni il viso neutro")
            self._set_header(context, "Recalibrating: keep a relaxed facial expression.")
            return {'RUNNING_MODAL'}

        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        # Un'eccezione non gestita in modal() termina l'operatore senza passare
        # da cancel(): webcam, timer e preview resterebbero aperti.
        try:
            # Il tempo fra due tick include tutto cio' che Blender fa fra uno e
            # l'altro (deformare le mesh, ridisegnare): se e' molto piu' lungo
            # del timer, la scena e' troppo pesante e il rig resta indietro.
            adesso = time.perf_counter()
            perf = self._perf
            if perf["ultimo"] is not None:
                perf["intervallo_s"] += adesso - perf["ultimo"]
                perf["tick"] += 1
            perf["ultimo"] = adesso
            esito = self._on_timer(context)
            perf["lavoro_s"] += time.perf_counter() - adesso
            return esito
        except Exception as e:
            traceback.print_exc()
            self.report({'ERROR'}, f"Motion capture stopped by an error: {e}")
            self.cancel(context)
            return {'CANCELLED'}

    def _on_timer(self, context: bpy.types.Context) -> set[str]:
        """Elabora un tick del timer: legge i landmark e aggiorna il rig."""
        if not self.settings.show_preview and self._tracker.show_preview:
            self._tracker.show_preview = False
        
        if not self._tracker.show_preview and self.settings.show_preview:
            self.settings.show_preview = False
            if self._area:
                self._area.tag_redraw()
        
        #reading landmarks information
        results = self._tracker.read_landmarks()
        if results is None:
            return {'PASS_THROUGH'}
        landmarks, aspect, t_frame = results.landmarks, results.aspect, results.time
        #ok
        head_frame = solver.build_head_frame(landmarks, aspect)
        if head_frame is None:
            return {'PASS_THROUGH'}
        #ok
        local = solver.to_head_local(landmarks, head_frame, self._track_idx, aspect)
        pose = solver.pose_from_matrix(results.pose)
        source_pose = solver.SourcePose(local=local,
                                        origin=head_frame.origin,
                                        scale=head_frame.scale,
                                        head_rotation=head_frame.rotation,
                                        pose_rotation=pose[0] if pose else None,
                                        pose_translation=pose[1] if pose else None,
                                        blendshapes=results.blendshapes)

        if self.retarget._neutral is None:
            self.retarget.accumulate_calibration(local, head_frame, source_pose)
            if self.retarget._calib_left > 0:
                self._set_header(context, "keep a relaxed facial expression.... %d" % self.retarget._calib_left)
            elif not self.retarget.finish_calibration(self._rig):
                #self.report({'WARNING'}, "Impossibile stimare la scala del rig: controlla le posizioni delle ossa.")
                self.report({'WARNING'}, "Unable to estimate rig's scale: check the bones' postions.")
                self.cancel(context)
                return {'CANCELLED'}
            else:
                self.report({'INFO'}, "Calibrated. Rig's scale: %.4f unit per width"
                                    "face. Table scale on console."
                                    % self.retarget._unit_scale)
                self._set_header(context, "Mocap actived | ESC = stop | C = Ricalibration")

        else:
            #function object is better
            if self._base_mocap:
                self._apply_pose(context, source_pose, t_frame)
                if config.DEBUG_MOCAP_LOG:
                    self._log_debug(context, source_pose, t_frame)
            else:
                target_pose = self.retarget.solve(self._rig, source_pose, self.mappings, self.settings, t_frame)
                self.apply_target(target_pose)
        if self._area:
            self._area.tag_redraw()

        return {'PASS_THROUGH'}

    def _set_header(self, context, text) -> None:
        if self._area:
            self._area.header_text_set("FaceMocap: " + text)

    def _get_track_index(self, rig):
        if rig.name == BASE_RIG_NAME:
            return TRACKED_INDICES
        return ADVANCE_TRACKED_INDICES

    def execute(self, context: bpy.types.Context) -> set[Literal['RUNNING_MODAL'] | Literal['CANCELLED'] | Literal['FINISHED'] | Literal['PASS_THROUGH'] | Literal['INTERFACE']]:
        self.settings = (context.scene.facemocap)
        self._base_mocap = False
        if properties.mapping_is_empty(self.settings):
                    properties.populate_default_mapping(self.settings)

        #if base rig is found so use it for the motion capture and avoid the advance motion capture 
        self._rig = find_rig(context)
        if self._rig:
            self._base_mocap = True
        else:
            self._rig = find_rig(context, self.settings.source_rig_name)
            if not self._rig:
                        self.report({'ERROR'}, f"FaceMocap source rig: {self.settings.source_rig_name} or the base rig: {BASE_RIG_NAME} not found. Generate it before starting.")
                        return {'CANCELLED'}
            self._target_rig = find_rig(context, self.settings.target_rig_name)
            if not self._target_rig:
                                    self.report({'ERROR'}, f"FaceMocap target rig: {self.settings.target_rig_name} not found.")
                                    return {'CANCELLED'}
            
        self._track_idx = self._get_track_index(self._rig)
        self.mappings = []

        for item in self.settings.mappings:
            source_bones = tuple(name.strip() for name in item.source_bones.split(",") if name.strip())
            self.mappings.append(
                MappingRuntime(
                    role=item.role,
                    target_bone=item.target_bone,
                    source=source_bones,
                    mode=item.mode,
                    gain=item.gain,
                    enable=item.enabled
                )
            )
        #handle different cameras
        try:
            self._tracker = FaceTracker(show_preview=self.settings.show_preview)
        except Exception as e:
            self.report({'ERROR'}, f"Unable to initialize MediaPipe: {e}")
            return {'CANCELLED'}
        if not self._tracker.start(self.settings.camera_id):
            self._tracker.stop()
            self._tracker = None
            self.report({'ERROR'}, f"Unable to start the webcam {self.settings.camera_id}.")
            return {'CANCELLED'}

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.select_all(action='DESELECT')
        self._rig.select_set(True)
        context.view_layer.objects.active = self._rig
        bpy.ops.object.mode_set(mode='POSE')

        self._area = context.area if context.area and context.area.type == 'VIEW_3D' else None
        #we should use the retarget for the calibration
        self.retarget.begin_calibration(self._rig)
        self._filters = {}
        self._perf = self._perf_vuote()
        self._set_header(context, "keep a relaxed facial expression...")

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.03, window=context.window)
        wm.modal_handler_add(self)

        self.report({'INFO'}, "Motion Capture started. Press ESC to stop, C to recalibrate.")
        return {'RUNNING_MODAL'}

    def cancel(self, context: bpy.types.Context) -> None:
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
            self._timer = None
        if self._tracker:
            self._tracker.stop()
            self._tracker = None
        if self._area:
            self._area.header_text_set(None)
            self._area = None
        self.report({'INFO'}, "Motion Capture stopped.")