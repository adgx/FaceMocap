"""Matematica del face solver: da landmark MediaPipe a offset per le pose bone."""

import math
import statistics

from mathutils import Matrix, Quaternion, Vector

from .config import (
    FACE_MAPPING,
    MAX_FEATURE_SCALE,
    MIN_FEATURE_SCALE,
    LM_FOREHEAD,
    LM_NASION,
    LM_SIDE_L,
    LM_SIDE_R,
    MAX_JAW_ANGLE,
    MIN_LEVER_DOWN,
    MIN_PAIR_DIST,
)

HEAD_TO_BLENDER = Matrix(((1.0, 0.0, 0.0),
                          (0.0, 0.0, -1.0),
                          (0.0, 1.0, 0.0)))


def landmark_point(landmarks, idx, aspect):
    """Landmark in coordinate isotrope per evitare che un movimento orizzontale
    e uno verticale della stessa lunghezza reale diano numeri diversi a causa
    dell'aspect ratio della webcam
    """
    lm = landmarks[idx]
    return Vector((lm.x * aspect, lm.y, lm.z * aspect))


def build_head_frame(landmarks, aspect):
    """Costruisce il sistema di riferimento della testa."""
    p_right = landmark_point(landmarks, LM_SIDE_R, aspect)
    p_left = landmark_point(landmarks, LM_SIDE_L, aspect)
    p_top = landmark_point(landmarks, LM_FOREHEAD, aspect)
    origin = landmark_point(landmarks, LM_NASION, aspect)

    side = p_left - p_right
    scale = side.length
    if scale < 1e-6:
        return None

    axis_l = side / scale
    up_raw = p_top - origin

    axis_f = axis_l.cross(up_raw) 
    if axis_f.length < 1e-6:
        return None
    axis_f.normalize()

    axis_u = axis_f.cross(axis_l)

    rot = Matrix((axis_l, axis_u, axis_f)).transposed()
    return origin, rot, scale


def to_head_local(landmarks, indices, origin, rot, scale, aspect):
    """Porta i landmark richiesti nel siste. di rif. testa-locale normalizzati"""
    rot_inv = rot.transposed()
    return {
        idx: (rot_inv @ (landmark_point(landmarks, idx, aspect) - origin)) / scale
        for idx in indices
    }


def mirrored_bone_name(name):
    if name.endswith("_L"):
        return name[:-2] + "_R"
    if name.endswith("_R"):
        return name[:-2] + "_L"
    return name


def mirror_rotation(rot):
    """Per specchiare l'asse delle X"""
    flip = Matrix(((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
    return flip @ rot @ flip


def head_rotation_matrix(rot_neutral, rot_current):
    relative = rot_neutral.transposed() @ rot_current
    return HEAD_TO_BLENDER @ relative @ HEAD_TO_BLENDER.transposed()


def head_local_to_blender(vec, mirror_x=False):
    """Vettore dal frame testa-locale agli assi armatura."""
    out = HEAD_TO_BLENDER @ vec
    if mirror_x:
        out.x = -out.x
    return out


def bone_anchor(bone):
    """Posizione in spazio armatura del landmark a cui l'osso e' agganciato."""
    anchor = bone.get("fm_anchor")
    if anchor is None or len(anchor) != 3:
        return bone.head_local.copy()
    return Vector(anchor)


def solve_unit_scale(armature, neutral_local, details=None):
    """Quante unita' Blender vale una larghezza di viso su QUESTO rig.

    Confronta le distanze fra le ancore delle ossa a riposo con le distanze fra
    i landmark corrispondenti in posa neutra: il rapporto mediano e' il fattore
    di conversione. Cosi' l'ampiezza e' corretta su qualunque modello, senza
    numeri da modificare a mano.
    """
    names = [n for n in FACE_MAPPING if n in armature.pose.bones]
    ratios = []

    for i, name_a in enumerate(names):
        idx_a = FACE_MAPPING[name_a].landmark
        if idx_a not in neutral_local:
            continue
        for name_b in names[i + 1:]:
            idx_b = FACE_MAPPING[name_b].landmark
            if idx_b not in neutral_local:
                continue

            mp_dist = (neutral_local[idx_a] - neutral_local[idx_b]).length
            if mp_dist < MIN_PAIR_DIST:
                continue

            anchor_a = bone_anchor(armature.pose.bones[name_a].bone)
            anchor_b = bone_anchor(armature.pose.bones[name_b].bone)
            rig_dist = (anchor_a - anchor_b).length
            if rig_dist < 1e-6:
                continue

            ratios.append(rig_dist / mp_dist)

    if details is not None:
        details["coppie"] = len(ratios)
        details["ossa"] = len(names)

    if not ratios:
        return None
    return statistics.median(ratios)


def solve_bone_scales(armature, neutral_local, global_scale, details=None):
    """Scala di conversione per ogni osso, in unita' Blender per larghezza viso."""
    scales = {}
    for name, data in FACE_MAPPING.items():
        ref = data.scale_ref
        scale = None
        info = {"ref": ref, "mp_dist": None, "rig_dist": None, "taglio": None}

        if ref:
            bone_a, bone_b = ref
            if bone_a in armature.pose.bones and bone_b in armature.pose.bones:
                idx_a = FACE_MAPPING[bone_a].landmark
                idx_b = FACE_MAPPING[bone_b].landmark
                if idx_a in neutral_local and idx_b in neutral_local:
                    mp_dist = (neutral_local[idx_a] - neutral_local[idx_b]).length
                    rig_dist = (bone_anchor(armature.pose.bones[bone_a].bone)
                                - bone_anchor(armature.pose.bones[bone_b].bone)).length
                    info["mp_dist"] = mp_dist
                    info["rig_dist"] = rig_dist
                    if mp_dist > 1e-4 and rig_dist > 1e-6:
                        scale = rig_dist / mp_dist

        if scale is None:
            scale = global_scale
        else:
            minimo = global_scale * MIN_FEATURE_SCALE
            massimo = global_scale * MAX_FEATURE_SCALE
            if scale < minimo:
                scale, info["taglio"] = minimo, "MIN_FEATURE_SCALE"
            elif scale > massimo:
                scale, info["taglio"] = massimo, "MAX_FEATURE_SCALE"

        scales[name] = scale
        if details is not None:
            info["scala"] = scale
            details[name] = info

    return scales


def is_valid_lever(lever):
    """Il vettore testa->coda come leva deve deve puntare verso il basso, cioe' stare sul mento."""
    return lever.length > 1e-6 and lever.z <= -MIN_LEVER_DOWN * lever.length


def solve_rotation_from_lever(pose_bone, tip_delta): # tip_delta e' lo spostamento del mento in spazio armatura
    """Rotazione che porta la coda dell'osso dove la vuole il tracking. Usata per la mandibola
    """
    pivot = pose_bone.bone.head_local
    rest_tip = pose_bone.bone.tail_local

    lever = rest_tip - pivot
    if not is_valid_lever(lever):
        return None

    target = lever + tip_delta
    if target.length < 1e-6:
        return None

    quat = lever.rotation_difference(target)

    max_angle = math.radians(MAX_JAW_ANGLE)
    if quat.angle > max_angle:
        quat = Quaternion(quat.axis, max_angle)

    return quat.to_matrix()


def to_bone_space(pose_bone, vec):
    """Da spostamento in spazio armatura a bone.location."""
    rest = pose_bone.bone.matrix_local.to_3x3()
    return rest.inverted() @ vec


def rotation_to_bone_space(pose_bone, rot):
    """Stessa conversione della precedente, per una rotazione."""
    rest = pose_bone.bone.matrix_local.to_3x3()
    return rest.inverted() @ rot @ rest
