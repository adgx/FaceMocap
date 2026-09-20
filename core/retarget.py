from . import solver

from dataclasses import dataclass

from .config import MotionMode

class RetargetSolver:
    def __init__(self) -> None:
        self.neutral = {}
        self.previous = {}
        self.neutral_head_rotation = None
        self.neutral_head_scale = 1.0

    def clear(self):
        self.neutral.clear()
        self.previous.clear()
        self.neutral_head_rotation = None
        self.neutral_head_scale = 1.0
        

    def calibrate(self, source_pose):
        self.neutral = {name: value.copy() for name, value in source_pose.local.items()}
        self.neutral_head_rotation = (source_pose.head_rotation.copy())
        self.neutral_head_scale = (source_pose.scale)
        self.previous.clear()

    def source_delta(self, source_pose, source_bone):
        curr = source_pose.local.get(source_bone)
        neutral = self.neutral.get(source_bone)

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
            res = value.copy()
        else:
            res = previous.lerp(val, alpha)
        self.previous[key] = res.copy()

        return res

    def smooth_quaternion(self, key, val, smoothing):
        alpha = 1.0 - max(0.0, min (0.999, smoothing))
        previous = self.previous.get(key)

        if previous is None:
            res = value.copy()
        else:
            res = previous.slerp(val, alpha)
        self.previous[key] = res.copy()

        return res
    
    def solve_translation(self, source_pose, mapping, mirror: bool = False):
        delta = self.average_delta(source_pose=source_pose, source_bones=mapping.source_bones)

        if delta is None:
            return None

        delta *= mapping.gain

        return solver.head_local_to_blender(delta, mirror)

    def solve_head_rotation(self, source_pose):
        if self.neutral_head_rotation is None:
            return Matrix.Identity(3)
        return solver.relative_rotation(source_pose.head_rotation, self.neutral_head_rotation)

    def solve_jaw_rotation(self, source_pose):
        required = ("LMK-Lip_corner.R", "LMK-Lip_corner.L", "LMK-Face_oval_chin")
        curr = []
        neutral = []

        for name in required:
            c = source_pose.local.get(name)
            n = self.neutral.get(name)

            if c is None or n is None:
                return Matrix.Identity(3)

            curr.append(c)
            neutral.append(n)

        curr_a = curr[0]
        curr_b = curr[1]
        curr_chin = curr[2]

        neutral_a = neutral[0]
        neutral_b = neutral[1]
        neutral_chin = neutral[2]

        curr_center = (curr_a + curr_b) * 0.5
        neutral_center = (neutral_a + neutral_b) * 0.5
        curr_frame = solver.make_frame(a=curr_a, b=curr_b, up=curr_chin - curr_center)

        if curr_frame is None:
            return Matrix.Identity(3)

        neutral_frame = solver.make_frame(neutral_a, neutral_b, neutral_chin - neutral_center)

        if neutral_frame is None:
            return Matrix.Identity(3)

        return solver.relative_rotation(curr_frame, neutral_frame)

    def solve(self, source_pose, mappings, smoothing, mirror):
        res = {}

        for mapping in mappings:
            #maybe remove this option
            if not mapping.enabled:
                continue
            if not mapping.target_bone:
                continue

            mode = mapping.mode

            if mode == MotionMode.TRANSLATION:
                val = self.solve_translation(source_pose, mapping, mirror)

                if val is None:
                    continue

                val = self.smooth_vector(mapping.role, val, smoothing)
                res[mapping.role] = ("TRANSLATION", val)
            elif mode == MotionMode.ROTATION:
                if mapping.role == "jaw":
                    rotation = (self.solve_jaw_rotation(source_pose))
                else: 
                    rotation = (self.solve_head_rotation(source_pose))
                rotation = (rotation.to_quaternion())
                rotation = (self.smooth_quaternion(mapping.role, rotation, smoothing))
                res[mapping.role] = ("ROTATION", rotation)

        return res
    #added: in this way is possible otain the default mapping and eventually modify it
    def get_default_retarget_map(self):

        res = {}

        for k, v in DEFAULT_RETARGET_MAP:
            res[k] = v

        return res