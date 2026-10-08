from . import solver
import time
from mathutils import Vector, Quaternion, Matrix

from dataclasses import dataclass

from .config import MotionMode, MappingRuntime, CALIBRATION_FRAMES, LANDMARKS_MAP
from .rig import reset_rig_pose, apply_rotation, apply_translation
from .solver import HeadFrame
from ..operators.diagnostics import stampa_tabella_scale
from .one_euro_filter import OneEuroFilter, OneEuroFilterQuaternion

class RetargetSolver:
    def __init__(self) -> None:
        self._calib_left = CALIBRATION_FRAMES
        self._calib_sum = {}
        self._calib_origin = Vector((0.0, 0.0, 0.0))
        self._calib_scale = 0.0
        self._calib_quats = []
        self._calib_pose_quats = []
        self._calib_pose_t = Vector((0.0, 0.0, 0.0))
        self._calib_blendshapes = {}
        self._calib_blendshape_count = 0

        self._neutral = None
        self._unit_scale = None
        self._bone_scales = {}
        self._warned_bones = set()
        self._neutral_rot = None
        self._neutral_pose_rot = None
        self._neutral_pose_t = None
        self._neutral_blendshapes = {}
        self._filters = {}

    def clear(self):
        self._filters.clear()
        self.neutral_head_rotation = None
        self.neutral_head_scale = 1.0

    def source_delta(self, source_pose, source_bone):
        id_mrk = LANDMARKS_MAP[source_bone].id_landmark
        curr = source_pose.local.get(id_mrk)
        neutral = self._neutral.get(id_mrk)

        if curr is None or neutral is None:
            return None

        return curr - neutral

    def average_delta(self, source_pose, source_bones):
        vals = []

        for bone in source_bones:
            delta = self.source_delta(source_pose=source_pose, source_bone=bone)

            if delta is not None:
                vals.append(delta)

        if not vals:
            return None
        res = Vector((0.0, 0.0, 0.0))

        for val in vals:
            res += val

        return res / len(vals)

    
    def solve_translation(self, source_pose, mapping, mirror: bool = False):
        delta = self.average_delta(source_pose=source_pose, source_bones=mapping.source)

        if delta is None:
            return None

        return solver.head_local_to_blender(delta, mirror) * self._translation_factor(mapping)

    def _translation_factor(self, mapping):
        """Unita' armatura per larghezza viso dell'osso sorgente, gain incluso.
        Se l'osso non ha una scala propria si usa quella globale del rig."""
        return mapping.gain * self._bone_scales.get(mapping.source[0], self._unit_scale)

    def _filter(self, key, filter_cls, settings):
        """Filtro 1Euro associato alla chiave, con i parametri correnti della UI."""
        flt = self._filters.get(key)
        if flt is None:
            flt = self._filters[key] = filter_cls()
        flt.min_cutoff = settings.min_cutoff
        flt.beta = settings.beta
        return flt

    def head_rotation(self, source_pose):
        """Rotazione della testa rispetto alla posa neutra, in assi armatura.
        Usa la matrice di posa MediaPipe se c'e', altrimenti i landmark."""
        if self._neutral_rot is None:
            return Matrix.Identity(3)
        if self._neutral_pose_rot is not None and source_pose.pose_rotation is not None:
            return solver.pose_rotation_matrix(self._neutral_pose_rot,
                                               source_pose.pose_rotation,
                                               self._neutral_rot)
        return solver.head_rotation_matrix(self._neutral_rot, source_pose.head_rotation)

    def solve_head_rotation(self, source_pose, mirror: bool = False):
        rot = self.head_rotation(source_pose)
        return solver.mirror_rotation(rot) if mirror else rot

    def solve_jaw_rotation(self, source_pose, source_bones, mirror: bool = False):
        curr = []
        neutral = []

        for name_mkr in source_bones:
            id_mrk = LANDMARKS_MAP[name_mkr].id_landmark
            c = source_pose.local.get(id_mrk)
            n = self._neutral.get(id_mrk)

            if c is None or n is None:
                return Matrix.Identity(3)

            curr.append(c)
            neutral.append(n)

        curr_a = curr[0]
        curr_b = curr[1]
        curr_c = curr[2]

        neutral_a = neutral[0]
        neutral_b = neutral[1]
        neutral_c = neutral[2]

        curr_center = (curr_a + curr_b) * 0.5
        neutral_center = (neutral_a + neutral_b) * 0.5
        curr_frame = solver.make_frame(a=curr_a, b=curr_b, up=curr_c - curr_center)

        if curr_frame is None:
            return Matrix.Identity(3)

        neutral_frame = solver.make_frame(neutral_a, neutral_b, neutral_c - neutral_center)

        if neutral_frame is None:
            return Matrix.Identity(3)

        # delta nel frame testa-locale -> assi armatura
        rot = solver.head_local_rotation_to_blender(solver.relative_rotation(curr_frame, neutral_frame))
        return solver.mirror_rotation(rot) if mirror else rot

    def solve(self, source_rig, source_pose, mappings: list[MappingRuntime], settings, t_now=None):
        res = {}
        if t_now is None:
            t_now = time.perf_counter()

        for mapping in mappings:
            if not mapping.enable:
                continue
            if not mapping.target_bone:
                continue

            mode = mapping.mode
            pose_bone = (source_rig.pose.bones.get(mapping.source[0]))

            if mode == MotionMode.TRANSLATION.value:
                val = self.solve_translation(source_pose, mapping, settings.mirror_x)

                if val is None:
                    continue

                flt = self._filter(mapping.role, OneEuroFilter, settings)
                flt.velocity_scale = self._translation_factor(mapping)
                val = flt.filter(val, t_now)

                res[mapping.role] = ("TRANSLATION", val)
                if pose_bone:
                    apply_translation(pose_bone, val)
            elif mode == MotionMode.ROTATION.value:
                if mapping.role == "Jaw":
                    rotation = self.solve_jaw_rotation(source_pose, mapping.source, settings.mirror_x)
                else: 
                    rotation = self.solve_head_rotation(source_pose, settings.mirror_x)
                rotation = rotation.to_quaternion()
                # il gain scala l'angolo (es. ripartizione fra Neck e Head)
                if abs(mapping.gain - 1.0) > 1e-6:
                    axis, angle = rotation.to_axis_angle()
                    rotation = Quaternion(axis, angle * mapping.gain)

                rotation = self._filter(mapping.role, OneEuroFilterQuaternion, settings).filter(rotation, t_now)
                res[mapping.role] = ("ROTATION", rotation)

        return res

    #ok
    def begin_calibration(self, rig) -> None:
        """Azzera la posa e riparte a raccogliere la posa neutra."""
        self._calib_left = CALIBRATION_FRAMES
        self._calib_sum = {}
        self._calib_origin = Vector((0.0, 0.0, 0.0))
        self._calib_scale = 0.0
        self._calib_quats = []
        self._calib_pose_quats = []
        self._calib_pose_t = Vector((0.0, 0.0, 0.0))
        self._calib_blendshapes = {}
        self._calib_blendshape_count = 0

        self._neutral = None
        self._unit_scale = None
        self._bone_scales = {}
        
        self._filters = {}

        if rig:
            reset_rig_pose(rig)

    #move to retarget class
    def accumulate_calibration(self, local, head_frame: HeadFrame, source_pose=None) -> None:
        for idx, vec in local.items():
            if idx in self._calib_sum:
                self._calib_sum[idx] += vec
            else:
                self._calib_sum[idx] = vec.copy()

        self._calib_origin += head_frame.origin
        self._calib_scale += head_frame.scale

        quat = head_frame.rotation.to_quaternion()
        if self._calib_quats and quat.dot(self._calib_quats[0]) < 0.0:
            quat.negate()
        self._calib_quats.append(quat)

        if source_pose is not None and source_pose.pose_rotation is not None:
            self._calib_pose_quats.append(source_pose.pose_rotation.to_quaternion())
            self._calib_pose_t += source_pose.pose_translation
        if source_pose is not None and source_pose.blendshapes:
            for name, score in source_pose.blendshapes.items():
                self._calib_blendshapes[name] = self._calib_blendshapes.get(name, 0.0) + score
            self._calib_blendshape_count += 1

        self._calib_left -= 1

    def finish_calibration(self, rig) -> bool:
        count = len(self._calib_quats)
        if count == 0:
            return False

        self._neutral = {idx: vec / count for idx, vec in self._calib_sum.items()}
        self._neutral_origin = self._calib_origin / count
        self._neutral_scale = self._calib_scale / count

        self._neutral_rot = _average_rotation(self._calib_quats)

        self._neutral_pose_rot = None
        self._neutral_pose_t = None
        if self._calib_pose_quats:
            self._neutral_pose_rot = _average_rotation(self._calib_pose_quats)
            self._neutral_pose_t = self._calib_pose_t / len(self._calib_pose_quats)

        self._neutral_blendshapes = {}
        if self._calib_blendshape_count:
            self._neutral_blendshapes = {name: total / self._calib_blendshape_count
                                         for name, total in self._calib_blendshapes.items()}

        dett_unit = {}
        self._unit_scale = solver.solve_unit_scale(rig, self._neutral, dett_unit)
        if self._unit_scale is None:
            #self.report({'WARNING'}, "Impossibile stimare la scala del rig: controlla le posizioni delle ossa.")
            #self.report({'WARNING'}, "Unable to estimate rig's scale: check the bones' postions.")
            return False
        
        dett_scale = {}
        self._bone_scales = solver.solve_bone_scales(rig, self._neutral, self._unit_scale, dett_scale)
        stampa_tabella_scale(self._unit_scale, dett_unit, dett_scale)

        return True


def _average_rotation(quats):
    """Media di rotazioni vicine fra loro, come matrice 3x3."""
    avg = Quaternion((0.0, 0.0, 0.0, 0.0))
    for quat in quats:
        if quat.dot(quats[0]) < 0.0:
            quat = -quat
        avg.w += quat.w
        avg.x += quat.x
        avg.y += quat.y
        avg.z += quat.z

    avg.normalize()
    return avg.to_matrix()
