from typing import NamedTuple

import bpy
from mathutils import Quaternion, Vector

from ..core import solver
from ..core import config
from ..core.config import FACE_MAPPING, LM_FOREHEAD, LM_NASION, LM_SIDE_L, LM_SIDE_R
from ..core.rig import find_rig
from ..core.webcam_core import FaceTracker
from .diagnostics import stampa_tabella_scale

TRACKED_INDICES = sorted(
    {data.landmark for data in FACE_MAPPING.values()}
    | {data.parent_landmark for data in FACE_MAPPING.values()
       if data.parent_landmark is not None}
    | {LM_SIDE_R, LM_SIDE_L, LM_FOREHEAD, LM_NASION}
)


def _gain_gruppo(bone_name):
    """Moltiplicatore d'ampiezza del gruppo a cui l'osso appartiene."""
    if bone_name == "Jaw" or bone_name.startswith(("Lip_", "Mouth_")):
        return config.MOUTH_GAIN
    if bone_name.startswith(("Eye_", "Eyelid_")):
        return config.EYE_GAIN
    if bone_name.startswith("Brow_"):
        return config.BROW_GAIN
    return 1.0


class _Voce(NamedTuple):
    osso: str
    landmark: int
    genitore: int
    landmark_speculare: int
    genitore_speculare: int
    gain: float               # gain per-osso gia' moltiplicato per quello di gruppo
    rotazione: bool           # osso a leva (mandibola) invece che in traslazione


def _piano_ossa():
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
        ))
    return voci


PIANO_OSSA = _piano_ossa()


def reset_rig_pose(rig):
    """Riporta a riposo le ossa gestite dal mocap."""
    for bone_name in FACE_MAPPING:
        pose_bone = rig.pose.bones.get(bone_name)
        if not pose_bone:
            continue
        pose_bone.location = (0.0, 0.0, 0.0)
        if pose_bone.rotation_mode == 'QUATERNION':
            pose_bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        else:
            pose_bone.rotation_euler = (0.0, 0.0, 0.0)


class FACEMOCAP_OT_reset_pose(bpy.types.Operator):
    """Riporta l'armatura alla rest pose"""
    bl_idname = "facemocap.reset_pose"
    bl_label = "Azzera Posa"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rig = find_rig(context)
        if not rig:
            self.report({'ERROR'}, "Armatura FaceMocap non trovata.")
            return {'CANCELLED'}
        reset_rig_pose(rig)
        return {'FINISHED'}


class FACEMOCAP_OT_start_capture(bpy.types.Operator):
    """Avvia la motion capture facciale. ESC per fermare, C per ricalibrare"""
    bl_idname = "facemocap.start_capture"
    bl_label = "Avvia Motion Capture"

    _timer = None
    _tracker = None
    _area = None
    _rig = None

    def _begin_calibration(self, context):
        """Azzera la posa e riparte a raccogliere la posa neutra."""
        self._calib_left = config.CALIBRATION_FRAMES
        self._calib_sum = {}
        self._calib_origin = Vector((0.0, 0.0, 0.0))
        self._calib_scale = 0.0
        self._calib_quats = []

        self._neutral = None
        self._unit_scale = None
        self._bone_scales = {}
        self._smoothed = {}
        self._smoothed_rot = {}
        self._warned_bones = set()
        self._smoothed_quat = Quaternion((1.0, 0.0, 0.0, 0.0))

        reset_rig_pose(self._rig)

    def _accumulate_calibration(self, local, origin, rot, scale):
        for idx, vec in local.items():
            if idx in self._calib_sum:
                self._calib_sum[idx] += vec
            else:
                self._calib_sum[idx] = vec.copy()

        self._calib_origin += origin
        self._calib_scale += scale

        quat = rot.to_quaternion()
        if self._calib_quats and quat.dot(self._calib_quats[0]) < 0.0:
            quat.negate()
        self._calib_quats.append(quat)

        self._calib_left -= 1

    def _finish_calibration(self, context):
        count = len(self._calib_quats)
        if count == 0:
            return False

        self._neutral = {idx: vec / count for idx, vec in self._calib_sum.items()}
        self._neutral_origin = self._calib_origin / count
        self._neutral_scale = self._calib_scale / count

        avg = Quaternion((0.0, 0.0, 0.0, 0.0))
        for quat in self._calib_quats:
            avg.w += quat.w
            avg.x += quat.x
            avg.y += quat.y
            avg.z += quat.z
        avg.normalize()
        self._neutral_rot = avg.to_matrix()

        dett_unit = {}
        self._unit_scale = solver.solve_unit_scale(self._rig, self._neutral, dett_unit)
        if self._unit_scale is None:
            self.report({'WARNING'}, "Impossibile stimare la scala del rig: controlla le posizioni delle ossa.")
            return False
        
        dett_scale = {}
        self._bone_scales = solver.solve_bone_scales(
            self._rig, self._neutral, self._unit_scale, dett_scale
        )

        stampa_tabella_scale(self._unit_scale, dett_unit, dett_scale)

        self.report({'INFO'}, "Calibrato. Scala rig: %.4f unita' per larghezza "
                    "viso. Tabella delle scale nella console di sistema."
                    % self._unit_scale)
        return True


    def _apply_pose(self, context, local, origin, rot, scale):
        settings = context.scene.facemocap
        alpha = 1.0 - config.SMOOTHING

        # Delta rispetto alla posa neutra, ancora in sist. di rif. testa-locale.
        deltas = {
            idx: vec - self._neutral[idx]
            for idx, vec in local.items()
            if idx in self._neutral
        }

        for voce in PIANO_OSSA:
            pose_bone = self._rig.pose.bones.get(voce.osso)
            if not pose_bone:
                continue

            if settings.mirror_x:
                lm_idx, parent_idx = voce.landmark_speculare, voce.genitore_speculare
            else:
                lm_idx, parent_idx = voce.landmark, voce.genitore

            if parent_idx is None:
                target = self._solve_head_translation(settings, origin, scale) * voce.gain
            else:
                if lm_idx not in deltas or parent_idx not in deltas:
                    continue
                relative = deltas[lm_idx] - deltas[parent_idx]
                scale_b = self._bone_scales.get(voce.osso, self._unit_scale)
                target = solver.head_local_to_blender(relative, settings.mirror_x) * (
                    scale_b * config.AMPLITUDE * voce.gain
                )

                if voce.rotazione:
                    if self._apply_lever_rotation(pose_bone, voce.osso, target, alpha):
                        continue
                    self._warn_bad_lever(voce.osso)

            previous = self._smoothed.get(voce.osso)
            smoothed = target if previous is None else previous.lerp(target, alpha)
            self._smoothed[voce.osso] = smoothed

            pose_bone.location = solver.to_bone_space(pose_bone, smoothed)

        self._apply_head_rotation(context, rot, alpha)

    def _warn_bad_lever(self, bone_name):
        """Avvisa una sola volta che l'osso non e' orientato come una leva."""
        if bone_name in self._warned_bones:
            return
        self._warned_bones.add(bone_name)
        self.report(
            {'WARNING'},
            "Osso '%s': la coda deve stare sul MENTO e la testa "
            "sull'articolazione vicino all'orecchio. Ora punta verso l'alto, "
            "quindi uso la traslazione. Rigenera l'armatura o riposiziona l'osso."
            % bone_name,
        )

    def _apply_lever_rotation(self, pose_bone, bone_name, tip_delta, alpha):
        """Applica a un osso a leva (la mandibola) la rotazione corrispondente."""
        armature_rot = solver.solve_rotation_from_lever(pose_bone, tip_delta)
        if armature_rot is None:
            return False

        bone_rot = solver.rotation_to_bone_space(pose_bone, armature_rot)
        quat = bone_rot.to_quaternion()

        previous = self._smoothed_rot.get(bone_name)
        quat = quat if previous is None else previous.slerp(quat, alpha)
        self._smoothed_rot[bone_name] = quat

        if pose_bone.rotation_mode != 'QUATERNION':
            pose_bone.rotation_mode = 'QUATERNION'
        pose_bone.rotation_quaternion = quat
        return True

    def _solve_head_translation(self, settings, origin, scale):
        """Spostamento della testa nello spazio, in unita' armatura."""
        #diviso per la scala corrente quinfi il risultato e' "quante larghezze di
        # viso si e' spostata la testa", quindi indipendente dalla distanza.
        offset = (origin - self._neutral_origin) / scale

        depth = (self._neutral_scale / scale - 1.0) * config.HEAD_DEPTH_GAIN

        vec = Vector((offset.x, depth, -offset.y))
        if settings.mirror_x:
            vec.x = -vec.x
        return vec * (self._unit_scale * config.HEAD_GAIN)

    def _apply_head_rotation(self, context, rot, alpha):
        pose_bone = self._rig.pose.bones.get("Head")
        if not pose_bone:
            return

        settings = context.scene.facemocap
        armature_rot = solver.head_rotation_matrix(self._neutral_rot, rot)
        if settings.mirror_x:
            armature_rot = solver.mirror_rotation(armature_rot)
        bone_rot = solver.rotation_to_bone_space(pose_bone, armature_rot)

        quat = bone_rot.to_quaternion()
        if abs(config.HEAD_GAIN - 1.0) > 1e-6:
            axis, angle = quat.to_axis_angle()
            quat = Quaternion(axis, angle * config.HEAD_GAIN)

        self._smoothed_quat = self._smoothed_quat.slerp(quat, alpha)

        if pose_bone.rotation_mode != 'QUATERNION':
            pose_bone.rotation_mode = 'QUATERNION'
        pose_bone.rotation_quaternion = self._smoothed_quat


    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'C' and event.value == 'PRESS':
            self._begin_calibration(context)
            self._set_header(context, "Ricalibrazione: mantieni il viso neutro")
            return {'RUNNING_MODAL'}

        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        lettura = self._tracker.read_landmarks()
        if lettura is None:
            return {'PASS_THROUGH'}
        landmarks, aspect = lettura

        head_frame = solver.build_head_frame(landmarks, aspect)
        if head_frame is None:
            return {'PASS_THROUGH'}
        origin, rot, scale = head_frame

        local = solver.to_head_local(landmarks, TRACKED_INDICES, origin, rot, scale, aspect)

        if self._neutral is None:
            self._accumulate_calibration(local, origin, rot, scale)
            if self._calib_left > 0:
                self._set_header(context, "Mantieni il viso neutro... %d" % self._calib_left)
            elif not self._finish_calibration(context):
                self.cancel(context)
                return {'CANCELLED'}
            else:
                self._set_header(context, "Mocap attivo | ESC = stop | C = ricalibra")
        else:
            self._apply_pose(context, local, origin, rot, scale)

        if self._area:
            self._area.tag_redraw()

        return {'PASS_THROUGH'}

    def _set_header(self, context, text):
        if self._area:
            self._area.header_text_set("FaceMocap: " + text)

    def execute(self, context):
        self._rig = find_rig(context)
        if not self._rig:
            self.report({'ERROR'}, "Armatura FaceMocap non trovata. Generala prima di avviare.")
            return {'CANCELLED'}

        self._tracker = FaceTracker()
        if not self._tracker.start():
            self.report({'ERROR'}, "Impossibile avviare la webcam.")
            return {'CANCELLED'}

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        self._rig.select_set(True)
        context.view_layer.objects.active = self._rig
        bpy.ops.object.mode_set(mode='POSE')

        self._area = context.area if context.area and context.area.type == 'VIEW_3D' else None
        self._begin_calibration(context)
        self._set_header(context, "Mantieni il viso neutro...")

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.03, window=context.window)
        wm.modal_handler_add(self)

        self.report({'INFO'}, "Motion Capture avviata. ESC per fermare, C per ricalibrare.")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
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
        self.report({'INFO'}, "Motion Capture fermata.")
