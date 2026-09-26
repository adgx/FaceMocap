from . import solver

from dataclasses import dataclass

from .config import MotionMode, MappingRuntime, CALIBRATION_FRAMES, LANDMARKS_MAP
from .rig import reset_rig_pose, apply_rotation, apply_translation
from .solver import HeadFrame
from ..operators.diagnostics import stampa_tabella_scale
from mathutils import Quaternion, Vector, Matrix

class RetargetSolver:
    def __init__(self) -> None:
        self._calib_left = CALIBRATION_FRAMES
        self._calib_sum = {}
        self._calib_origin = Vector((0.0, 0.0, 0.0))
        self._calib_scale = 0.0
        self._calib_quats = []

        self._neutral = {}
        self._unit_scale = None
        self._bone_scales = {}
        self._smoothed = {}
        self._smoothed_rot = {}
        self._warned_bones = set()
        self._smoothed_quat = Quaternion((1.0, 0.0, 0.0, 0.0))
        self._neutral_rot = None
        self.previous = {}

    def clear(self):
        self.previous.clear()
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

    def smooth_vector(self, key, val, smoothing):
        alpha = 1.0 - max(0.0, min (0.999, smoothing))
        previous = self.previous.get(key)

        if previous is None:
            res = val.copy()
        else:
            res = previous.lerp(val, alpha)
        self.previous[key] = res.copy()

        return res

    def smooth_quaternion(self, key, val, smoothing):
        alpha = 1.0 - max(0.0, min (0.999, smoothing))
        previous = self.previous.get(key)

        if previous is None:
            res = val.copy()
        else:
            res = previous.slerp(val, alpha)
        self.previous[key] = res.copy()

        return res
    
    def solve_translation(self, source_pose, mapping, mirror: bool = False):
        delta = self.average_delta(source_pose=source_pose, source_bones=mapping.source)

        if delta is None:
            return None

        delta *= mapping.gain

        return solver.head_local_to_blender(delta, mirror)*self._bone_scales.get(mapping.source[0])

    def solve_head_rotation(self, source_pose):
        if self._neutral_rot is None:
            return Matrix.Identity(3)
        return solver.relative_rotation(source_pose.head_rotation, self._neutral_rot)

    def solve_jaw_rotation(self, source_pose, source_bones):
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

        return solver.relative_rotation(curr_frame, neutral_frame)

    def solve(self, source_rig, source_pose, mappings: list[MappingRuntime], smoothing, mirror):
        res = {}

        for mapping in mappings:
            if not mapping.enable:
                continue
            if not mapping.target_bone:
                continue

            mode = mapping.mode
            pose_bone = (source_rig.pose.bones.get(mapping.source[0]))

            if mode == MotionMode.TRANSLATION.value:
                val = self.solve_translation(source_pose, mapping, mirror)

                if val is None:
                    continue

                val = self.smooth_vector(mapping.role, val, smoothing)
                res[mapping.role] = ("TRANSLATION", val)
                apply_translation(pose_bone, val)
            elif mode == MotionMode.ROTATION.value:
                if mapping.role == "Jaw":
                    rotation = (self.solve_jaw_rotation(source_pose, mapping.source))
                else: 
                    rotation = (self.solve_head_rotation(source_pose))
                rotation = (rotation.to_quaternion())
                rotation = (self.smooth_quaternion(mapping.role, rotation, smoothing))
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

        self._neutral = None
        self._unit_scale = None
        self._bone_scales = {}
        self._smoothed = {}
        self._smoothed_rot = {}
        self._warned_bones = set()
        self._smoothed_quat = Quaternion((1.0, 0.0, 0.0, 0.0))

        reset_rig_pose(rig)

    #move to retarget class
    def accumulate_calibration(self, local, head_frame: HeadFrame) -> None:
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

        self._calib_left -= 1

    def finish_calibration(self, rig) -> bool:
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
        self._unit_scale = solver.solve_unit_scale(rig, self._neutral, dett_unit)
        if self._unit_scale is None:
            #self.report({'WARNING'}, "Impossibile stimare la scala del rig: controlla le posizioni delle ossa.")
            #self.report({'WARNING'}, "Unable to estimate rig's scale: check the bones' postions.")
            return False
        
        dett_scale = {}
        self._bone_scales = solver.solve_bone_scales(rig, self._neutral, self._unit_scale, dett_scale)
        stampa_tabella_scale(self._unit_scale, dett_unit, dett_scale)

        return True