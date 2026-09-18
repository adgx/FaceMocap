from enum import Enum
from typing import NamedTuple
from dataclasses import dataclass
from mathutils import Vector, Quaternion

class MotionMode(Enum):
    HEAD = "HEAD"
    LANDMARK = "LANDMARK"
    RELATIVE = "RELATIVE"
    TRANSLATION = "TRANSLATION"

@dataclass
class LandmarkSample:
    idx: int
    pos: Vector
    neutral_pos: Vector
    delta: Vector

@dataclass(frozen=True)
class LandmarkBoneMap:
    bone: str
    landmark: int
    parent_landmark: int | None
    parent_bone: str | None
    rest_position: tuple[float, float, float]
    gaint: float = 1.0
    rot_axis: tuple[float, float, float] | None = None
    motion_mode: MotionMode = MotionMode.LANDMARK
    rot_landmarks: tuple[int, ...] = ()

class BoneMap(NamedTuple):
    landmark: int               # indice MediaPipe che pilota l'osso
    parent_landmark: int        # landmark del genitore, None per la radice
    parent_bone: str            # nome dell'osso genitore, None per la radice
    position: tuple             # (x, y, z) normalizzati in [-1, 1] sulle semi-dimensioni
    gain: float                 # ampiezza relativa dentro la sua feature
    scale_ref: tuple            # coppia di ossa che misura la feature, None = larghezza viso
    motion_mode: MotionMode     #type of motion to apply on the bone


_EYE_L = ("Eyelid_Up.L", "Eyelid_Low.L")    # apertura occhio sinistro
_EYE_R = ("Eyelid_Up.R", "Eyelid_Low.R")    # apertura occhio destro
_MOUTH = ("Mouth_Corner.L", "Mouth_Corner.R")   # larghezza bocca

_TABELLA = {
    "Head":           (1,   None, None,   (0.0,  0.0,  0.0),   1.0, None, MotionMode.HEAD),
    # La mandibola e' pilotata in ROTAZIONE
    "Jaw":            (152, 1,    "Head", (0.0,  0.30, 0.05),  1.0, None, MotionMode.RELATIVE),

    # centro dell'iride dell'occhio
    "Eye.L":          (473, 1,    "Head", (0.2, -0.2,  0.2),   1.0, None, MotionMode.RELATIVE),
    "Eye.R":          (468, 1,    "Head", (-0.2, -0.2,  0.2),  1.0, None, MotionMode.RELATIVE),

    # Palpebre
    "Eyelid_Up.L":    (386, 1,    "Head", (0.2, -0.22, 0.26),  1.15, _EYE_L, MotionMode.RELATIVE),
    "Eyelid_Low.L":   (374, 1,    "Head", (0.2, -0.22, 0.14),  1.15, _EYE_L, MotionMode.RELATIVE),
    "Eyelid_Up.R":    (159, 1,    "Head", (-0.2, -0.22, 0.26), 1.15, _EYE_R, MotionMode.RELATIVE),
    "Eyelid_Low.R":   (145, 1,    "Head", (-0.2, -0.22, 0.14), 1.15, _EYE_R, MotionMode.RELATIVE),

    "Brow.L":         (334, 1,    "Head", (0.2, -0.25, 0.4),   1.2, None, MotionMode.RELATIVE),
    "Brow.R":         (105, 1,    "Head", (-0.2, -0.25, 0.4),  1.2, None, MotionMode.RELATIVE),

    # Labbra: 5 punti di controllo per labbro (angolo, meta', centro, meta',
    # angolo).
    "Lip_Upper":      (0,   1,    "Head", (0.0, -0.2, -0.24),       0.7, _MOUTH, MotionMode.RELATIVE),
    "Lip_Upper.L":    (269, 1,    "Head", (0.08, -0.18, -0.26),     0.7, _MOUTH, MotionMode.RELATIVE),
    "Lip_Upper.R":    (39,  1,    "Head", (-0.08, -0.18, -0.26),    0.7, _MOUTH, MotionMode.RELATIVE),
    "Lip_Lower":      (17,  152,  "Jaw",  (0.0, -0.2, -0.36),       1.0, _MOUTH, MotionMode.RELATIVE),
    "Lip_Lower.L":    (405, 152,  "Jaw",  (0.08, -0.18, -0.34),     1.0, _MOUTH, MotionMode.RELATIVE),
    "Lip_Lower.R":    (181, 152,  "Jaw",  (-0.08, -0.18, -0.34),    1.0, _MOUTH, MotionMode.RELATIVE),

    "Mouth_Corner.L": (291, 152,  "Jaw",  (0.15, -0.15, -0.3),      1.0, _MOUTH, MotionMode.RELATIVE),
    "Mouth_Corner.R": (61,  152,  "Jaw",  (-0.15, -0.15, -0.3),     1.0, _MOUTH, MotionMode.RELATIVE),
}

#landmark mapping (source skeleton)
_LANDMARKS_MAP = {
    ##################################################################
    #                              Lips                              #
    ##################################################################
    "LMK-Lip_corner.R":         LandmarkBoneMap(bone="LMK-Lip_corner.R",    landmark=61,    parent_landmark=None,   parent_bone="LMK-Root",   rest_position=(-0.033,  -0.063,     0.269),     motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_corner.L":         LandmarkBoneMap(bone="LMK-Lip_corner.L",    landmark=291,   parent_landmark=None,   parent_bone="LMK-Root",   rest_position=(0.033,   -0.063,     0.269),     motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_main_upp":         LandmarkBoneMap(bone="LMK-Lip_main_upp",    landmark=0,     parent_landmark=None,   parent_bone="LMK-Root",   rest_position=(0.0,     -0.085,     0.282),     motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_upp1.R":           LandmarkBoneMap(bone="LMK-Lip_upp1.R",      landmark=37,    parent_landmark=None,   parent_bone="LMK-Root",   rest_position=(-0.011,   -0.085,     0.281),    motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_upp2.R":           LandmarkBoneMap(bone="LMK-Lip_upp2.R",      landmark=39,    parent_landmark=None,   parent_bone="LMK-Root",   rest_position=(-0.019,   -0.078,     0.279),    motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_upp1.L":           LandmarkBoneMap(bone="LMK-Lip_upp1.L",      landmark=267,   parent_landmark=None,   parent_bone="LMK-Root",   rest_position=(0.011,   -0.085,     0.281),     motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_upp2.L":           LandmarkBoneMap(bone="LMK-Lip_upp2.L",      landmark=269,   parent_landmark=None,   parent_bone="LMK-Root",   rest_position=(0.019,   -0.078,     0.279),     motion_mode=MotionMode.LANDMARK),
    
    "LMK-Lip_main_low":         LandmarkBoneMap(bone="LMK-Lip_main_low",     landmark=17,    parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.0,    -0.078,   0.257), motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_low1.R":           LandmarkBoneMap(bone="LMK-Lip_low1.R",       landmark=84,    parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.012,  -0.076, 0.257),  motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_low2.R":           LandmarkBoneMap(bone="LMK-Lip_low2.R",       landmark=181,   parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.020,  -0.072, 0.257),  motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_low1.L":           LandmarkBoneMap(bone="LMK-Lip_low1.L",       landmark=314,   parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.012,  -0.076, 0.257),   motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_low2.L":           LandmarkBoneMap(bone="LMK-Lip_low2.L",       landmark=405,   parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.020,  -0.072, 0.257),   motion_mode=MotionMode.LANDMARK),

    ##################################################################
    #                              Eye                               #
    ##################################################################
    "LMK-Eye.L":          LandmarkBoneMap(bone="LMK-Eye.L", landmark=474, parent_landmark=None,    parent_bone="LMK-Root",  rest_position=(0.049,    -0.133,  0.378), motion_mode=MotionMode.LANDMARK),
    "LMK-Eye.R":          LandmarkBoneMap(bone="LMK-Eye.R", landmark=469, parent_landmark=None,    parent_bone="LMK-Root",  rest_position=(-0.049,   -0.133,  0.378), motion_mode=MotionMode.LANDMARK),

    ##################################################################
    #                            Eyelid                              #
    ##################################################################
    "LMK-Eyelid_corner_in.L":   (398, None,    "LMK-Root", (0.025, -0.048, 0.372),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_upp1.L":        (384, None,    "LMK-Root", (0.039, -0.051, 0.382),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_upp2.L":        (386, None,    "LMK-Root", (0.052, -0.054, 0.384),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_upp3.L":        (388, None,    "LMK-Root", (0.067, -0.047, 0.382),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_corner_out.L":  (263, None,    "LMK-Root", (0.073, -0.035, 0.378),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_low1.L":        (381, None,    "LMK-Root", (0.040, -0.049, 0.372),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_low2.L":        (374, None,    "LMK-Root", (0.053, -0.050, 0.370),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_low3.L":        (390, None,    "LMK-Root", (0.066, -0.040, 0.374),  1.0, None, MotionMode.LANDMARK),

    "LMK-Eyelid_corner_in.R":   (133, None,    "LMK-Root", (-0.025, -0.048, 0.372),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_upp1.R":        (157, None,    "LMK-Root", (-0.039, -0.051, 0.382),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_upp2.R":        (159, None,    "LMK-Root", (-0.052, -0.054, 0.384),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_upp3.R":        (161, None,    "LMK-Root", (-0.067, -0.047, 0.382),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_corner_out.R":  (33,  None,    "LMK-Root", (-0.073, -0.035, 0.378),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_low1.R":        (154, None,    "LMK-Root", (-0.040, -0.049, 0.372),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_low2.R":        (145, None,    "LMK-Root", (-0.053, -0.050, 0.370),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_low3.R":        (163, None,    "LMK-Root", (-0.066, -0.040, 0.374),  1.0, None, MotionMode.LANDMARK),
    
    ##################################################################
    #                              BROW                              #
    ##################################################################
    "LMK-Brow1.L":         (336, None,    "LMK-Root", (0.039, -0.078, 0.418),   1.0, None, MotionMode.LANDMARK),
    "LMK-Brow2.L":         (334, None,    "LMK-Root", (0.077, -0.056, 0.420),   1.0, None, MotionMode.LANDMARK),
    "LMK-Brow3.L":         (300, None,    "LMK-Root", (0.098, -0.018, 0.408),   1.0, None, MotionMode.LANDMARK),
    "LMK-Brow1.R":         (107, None,    "LMK-Root", (-0.039, -0.078, 0.418),  1.0, None, MotionMode.LANDMARK),
    "LMK-Brow2.R":         (105, None,    "LMK-Root", (-0.077, -0.056, 0.420),  1.0, None, MotionMode.LANDMARK),
    "LMK-Brow3.R":         (70,  None,    "LMK-Root", (-0.098, -0.018, 0.408),  1.0, None, MotionMode.LANDMARK),
    
    ##################################################################
    #                            FACE OVAL                           #
    ##################################################################
    "LMK-Face_oval1.L":         (338, None,    "LMK-Root", (0.038, -0.063, 0.472),      1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval2.L":         (332, None,    "LMK-Root", (0.082, -0.035, 0.461),      1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval3.L":         (454, None,    "LMK-Root", (0.11, 0.054, 0.36),         1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval4.L":         (361, None,    "LMK-Root", (0.106, 0.061, 0.316),       1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval5.L":         (379, None,    "LMK-Root", (0.057, -0.016, 0.233),      1.0, None, MotionMode.LANDMARK),
    
    "LMK-Face_oval_chin":       (152, None,    "LMK-Root", (0.0, -0.056, 0.206),   1.0, None, MotionMode.LANDMARK),
    
    "LMK-Face_oval1.R":         (109, None,    "LMK-Root", (-0.038, -0.063, 0.472),     1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval2.R":         (103, None,    "LMK-Root", (-0.082, -0.035, 0.461),     1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval3.R":         (234, None,    "LMK-Root", (-0.11, 0.054, 0.36),        1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval4.R":         (132, None,    "LMK-Root", (-0.106, 0.061, 0.316),      1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval5.R":         (150, None,    "LMK-Root", (-0.057, -0.016, 0.233),     1.0, None, MotionMode.LANDMARK),
    ##################################################################
    #                            NOSE                                #
    ##################################################################
    "LMK-Nose_tip":          (4,    None,    "LMK-Root", (0.0, -0.112, 0.314),      1.0, None, MotionMode.LANDMARK),
    "LMK-Nose_base":         (168,  None,    "LMK-Root", (0.0, -0.083, 0.381),      1.0, None, MotionMode.LANDMARK),
    "LMK-Nostril.L":         (358,  None,    "LMK-Root", (0.031, -0.069, 0.311),    1.0, None, MotionMode.LANDMARK),
    "LMK-Nostril.R":         (129,  None,    "LMK-Root", (-0.031, -0.069, 0.311),   1.0, None, MotionMode.LANDMARK),

    ##################################################################
    #                            CHEEK                               #
    ##################################################################
    "LMK-Cheek_upp.L":          (280, None,    "LMK-Root", (0.078, -0.043, 0.339),   1.0, None, MotionMode.LANDMARK),
    "LMK-Cheek_low.L":          (426, None,    "LMK-Root", (0.054, -0.056, 0.290),   1.0, None, MotionMode.LANDMARK),
    "LMK-Cheek_in.L":           (266, None,    "LMK-Root", (0.044, -0.062, 0.329),   1.0, None, MotionMode.LANDMARK),
    "LMK-Cheek_out.L":          (416, None,    "LMK-Root", (0.079, -0.021, 0.284),   1.0, None, MotionMode.LANDMARK),

    "LMK-Cheek_upp.R":          (50,    None,    "LMK-Root", (-0.078, -0.043, 0.339),   1.0, None, MotionMode.LANDMARK),
    "LMK-Cheek_low.R":          (206,   None,    "LMK-Root", (-0.054, -0.056, 0.290),   1.0, None, MotionMode.LANDMARK),
    "LMK-Cheek_in.R":           (36,    None,    "LMK-Root", (-0.044, -0.062, 0.329),   1.0, None, MotionMode.LANDMARK),
    "LMK-Cheek_out.R":          (192,   None,    "LMK-Root", (-0.079, -0.021, 0.284),   1.0, None, MotionMode.LANDMARK),

}

#landmark bones (source skeleton)
#notes display these as bbone
_LANDMARKS_BONES_LUT = {
    ##################################################################
    #                              Lips                              #
    ##################################################################
    "LMK-Lip_corner.R":         (61,    None,   "LMK-Root",   (-0.033,  -0.063,     0.269),     1.0, None, MotionMode.LANDMARK),
    "LMK-Lip_corner.L":         (291,   None,   "LMK-Root",   (0.033,   -0.063,     0.269),     1.0, None, MotionMode.LANDMARK),
    "LMK-Lip_main_upp":         (0,     None,   "LMK-Root",   (0.0,     -0.085,     0.282),     1.0, None, MotionMode.LANDMARK),
    "LMK-Lip_upp1.R":           (37,    None,   "LMK-Root",   (-0.011,   -0.085,     0.281),    1.0, None, MotionMode.LANDMARK),
    "LMK-Lip_upp2.R":           (39,    None,   "LMK-Root",   (-0.019,   -0.078,     0.279),    1.0, None, MotionMode.LANDMARK),
    "LMK-Lip_upp1.L":           (267,   None,   "LMK-Root",   (0.011,   -0.085,     0.281),     1.0, None, MotionMode.LANDMARK),
    "LMK-Lip_upp2.L":           (269,   None,   "LMK-Root",   (0.019,   -0.078,     0.279),     1.0, None, MotionMode.LANDMARK),
    
    "LMK-Lip_main_low":         (17,    None,    "LMK-Root", (0.0,    -0.078,   0.257),     1.0, None, MotionMode.LANDMARK),
    "LMK-Lip_low1.R":           (84,    None,    "LMK-Root", (-0.012,  -0.076, 0.257),      1.0, None, MotionMode.LANDMARK),
    "LMK-Lip_low2.R":           (181,   None,    "LMK-Root", (-0.020,  -0.072, 0.257),      1.0, None, MotionMode.LANDMARK),
    "LMK-Lip_low1.L":           (314,   None,    "LMK-Root", (0.012,  -0.076, 0.257),       1.0, None, MotionMode.LANDMARK),
    "LMK-Lip_low2.L":           (405,   None,    "LMK-Root", (0.020,  -0.072, 0.257),       1.0, None, MotionMode.LANDMARK),

    ##################################################################
    #                              Eye                               #
    ##################################################################
    "LMK-Eye.L":          (474, None,    "LMK-Root",  (0.049,    -0.133,  0.378),   1.0, None, MotionMode.LANDMARK),
    "LMK-Eye.R":          (469, None,    "LMK-Root",  (-0.049,   -0.133,  0.378),   1.0, None, MotionMode.LANDMARK),

    ##################################################################
    #                            Eyelid                              #
    ##################################################################
    "LMK-Eyelid_corner_in.L":   (398, None,    "LMK-Root", (0.025, -0.048, 0.372),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_upp1.L":        (384, None,    "LMK-Root", (0.039, -0.051, 0.382),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_upp2.L":        (386, None,    "LMK-Root", (0.052, -0.054, 0.384),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_upp3.L":        (388, None,    "LMK-Root", (0.067, -0.047, 0.382),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_corner_out.L":  (263, None,    "LMK-Root", (0.073, -0.035, 0.378),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_low1.L":        (381, None,    "LMK-Root", (0.040, -0.049, 0.372),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_low2.L":        (374, None,    "LMK-Root", (0.053, -0.050, 0.370),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_low3.L":        (390, None,    "LMK-Root", (0.066, -0.040, 0.374),  1.0, None, MotionMode.LANDMARK),

    "LMK-Eyelid_corner_in.R":   (133, None,    "LMK-Root", (-0.025, -0.048, 0.372),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_upp1.R":        (157, None,    "LMK-Root", (-0.039, -0.051, 0.382),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_upp2.R":        (159, None,    "LMK-Root", (-0.052, -0.054, 0.384),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_upp3.R":        (161, None,    "LMK-Root", (-0.067, -0.047, 0.382),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_corner_out.R":  (33,  None,    "LMK-Root", (-0.073, -0.035, 0.378),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_low1.R":        (154, None,    "LMK-Root", (-0.040, -0.049, 0.372),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_low2.R":        (145, None,    "LMK-Root", (-0.053, -0.050, 0.370),  1.0, None, MotionMode.LANDMARK),
    "LMK-Eyelid_low3.R":        (163, None,    "LMK-Root", (-0.066, -0.040, 0.374),  1.0, None, MotionMode.LANDMARK),
    
    ##################################################################
    #                              BROW                              #
    ##################################################################
    "LMK-Brow1.L":         (336, None,    "LMK-Root", (0.039, -0.078, 0.418),   1.0, None, MotionMode.LANDMARK),
    "LMK-Brow2.L":         (334, None,    "LMK-Root", (0.077, -0.056, 0.420),   1.0, None, MotionMode.LANDMARK),
    "LMK-Brow3.L":         (300, None,    "LMK-Root", (0.098, -0.018, 0.408),   1.0, None, MotionMode.LANDMARK),
    "LMK-Brow1.R":         (107, None,    "LMK-Root", (-0.039, -0.078, 0.418),  1.0, None, MotionMode.LANDMARK),
    "LMK-Brow2.R":         (105, None,    "LMK-Root", (-0.077, -0.056, 0.420),  1.0, None, MotionMode.LANDMARK),
    "LMK-Brow3.R":         (70,  None,    "LMK-Root", (-0.098, -0.018, 0.408),  1.0, None, MotionMode.LANDMARK),
    
    ##################################################################
    #                            FACE OVAL                           #
    ##################################################################
    "LMK-Face_oval1.L":         (338, None,    "LMK-Root", (0.038, -0.063, 0.472),      1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval2.L":         (332, None,    "LMK-Root", (0.082, -0.035, 0.461),      1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval3.L":         (454, None,    "LMK-Root", (0.11, 0.054, 0.36),         1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval4.L":         (361, None,    "LMK-Root", (0.106, 0.061, 0.316),       1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval5.L":         (379, None,    "LMK-Root", (0.057, -0.016, 0.233),      1.0, None, MotionMode.LANDMARK),
    
    "LMK-Face_oval_chin":       (152, None,    "LMK-Root", (0.0, -0.056, 0.206),   1.0, None, MotionMode.LANDMARK),
    
    "LMK-Face_oval1.R":         (109, None,    "LMK-Root", (-0.038, -0.063, 0.472),     1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval2.R":         (103, None,    "LMK-Root", (-0.082, -0.035, 0.461),     1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval3.R":         (234, None,    "LMK-Root", (-0.11, 0.054, 0.36),        1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval4.R":         (132, None,    "LMK-Root", (-0.106, 0.061, 0.316),      1.0, None, MotionMode.LANDMARK),
    "LMK-Face_oval5.R":         (150, None,    "LMK-Root", (-0.057, -0.016, 0.233),     1.0, None, MotionMode.LANDMARK),
    ##################################################################
    #                            NOSE                                #
    ##################################################################
    "LMK-Nose_tip":          (4,    None,    "LMK-Root", (0.0, -0.112, 0.314),      1.0, None, MotionMode.LANDMARK),
    "LMK-Nose_base":         (168,  None,    "LMK-Root", (0.0, -0.083, 0.381),      1.0, None, MotionMode.LANDMARK),
    "LMK-Nostril.L":         (358,  None,    "LMK-Root", (0.031, -0.069, 0.311),    1.0, None, MotionMode.LANDMARK),
    "LMK-Nostril.R":         (129,  None,    "LMK-Root", (-0.031, -0.069, 0.311),   1.0, None, MotionMode.LANDMARK),

    ##################################################################
    #                            CHEEK                               #
    ##################################################################
    "LMK-Cheek_upp.L":          (280, None,    "LMK-Root", (0.078, -0.043, 0.339),   1.0, None, MotionMode.LANDMARK),
    "LMK-Cheek_low.L":          (426, None,    "LMK-Root", (0.054, -0.056, 0.290),   1.0, None, MotionMode.LANDMARK),
    "LMK-Cheek_in.L":           (266, None,    "LMK-Root", (0.044, -0.062, 0.329),   1.0, None, MotionMode.LANDMARK),
    "LMK-Cheek_out.L":          (416, None,    "LMK-Root", (0.079, -0.021, 0.284),   1.0, None, MotionMode.LANDMARK),

    "LMK-Cheek_upp.R":          (50,    None,    "LMK-Root", (-0.078, -0.043, 0.339),   1.0, None, MotionMode.LANDMARK),
    "LMK-Cheek_low.R":          (206,   None,    "LMK-Root", (-0.054, -0.056, 0.290),   1.0, None, MotionMode.LANDMARK),
    "LMK-Cheek_in.R":           (36,    None,    "LMK-Root", (-0.044, -0.062, 0.329),   1.0, None, MotionMode.LANDMARK),
    "LMK-Cheek_out.R":          (192,   None,    "LMK-Root", (-0.079, -0.021, 0.284),   1.0, None, MotionMode.LANDMARK),

}

#destination rig
_ADVANCE_RIG_BONES_LUT = {
    #Deformation bones = 5
    #Master bones = 2
    #Control bones = 14
    #Target bones = 2
    #Parent bones = 4
    #Total bones to control = 27

    ##################################################################
    #                      Deformation bones                         #
    ##################################################################

    #Neck:
    #DEF-Neck2 from laryngeal prominance to the base of jaw (only rotation)
    #Head:
    #DEF-Head (only rotation)
    #Jaw:
    #DEF-Jaw at the base of ears (only rotation)
    #Nose:
    #DEF-Nostril.L at the nostril of the nose (only translation)
    #DEF-Nostril.R at the nostril of the nose (only translation)

    ##################################################################
    #                      Master bones                              #
    ##################################################################
    
    #Jawline:
    #MSTR-Jawline.L -> at the center between the three jawline def bones (only translation)
    #MSTR-Jawline.R -> at the center between the three jawline def bones (only translation)

    ##################################################################
    #                      Control bones                             #
    ##################################################################
    
    #Lips:
    #CLT-Lip_main_upp place it on the upper center of the lip loop (only translation)
    #CLT-Lip_local_upp.L is a controller between the  main and the conner  (only translation)
    #CLT-Lip_corn.L place it on the left corner of the lip loop (only translation)
    #CLT-Lip_local_upp.R is a controller between the  main and the conner (only translation)
    #CLT-Lip_corn.R place it on the left corner of the lip loop (only translation)
    #CLT-Lip_local_low.R is a controller between the  main and the conner (only translation)
    #CLT-Lip_main_low place it on the lower center of the lip loop (only translation)
    #CLT-Lip_local_low.L is a controller between the  main and the conner (only translation)
    #Brow:
    #CTL-Brow_in.L  controller for the most inner part of brow (only translation)
    #CTL-Brow_mid.L controller for the midle part of brow  (only translation)
    #CTL-Brow_out.L controller for the most outer part of brow (only translation)
    #CTL-Brow_in.R  controller for the most inner part of brow (only translation)
    #CTL-Brow_mid.R controller for the midle part of brow  (only translation)
    #CTL-Brow_out.R controller for the most outer part of brow (only translation)
     
    ##################################################################
    #                      Target bones                              #
    ##################################################################
    
    #Eye:
    #TGT-Eye.L used to control the eye direction (only translation)
    #TGT-Eye.R used to control the eye direction (only translation)

    ##################################################################
    #                      Parent bones                              #
    ##################################################################
    
    #Eyelid:
    #P-Eyelid_upp.L used to control the upper eyelid position (only translation)
    #P-Eyelid_upp.R used to control the upper eyelid position (only translation)
    #P-Eyelid_low.L used to control the lower eyelid position (only translation)
    #P-Eyelid_low.R used to control the lower eyelid position (only translation) 
}

FACE_MAPPING = {nome: BoneMap(*riga) for nome, riga in _TABELLA.items()}
LANDMARKERS_FACE_MAPPING = {nome: BoneMap(*riga) for nome, riga in _LANDMARKS_BONES_LUT.items()}
#ossa per la rotazione della mandibola con centro di rotazione all'altezza delle orecchie
ROTATION_BONES = {
    "Jaw": ((0.0, 0.30, 0.05), (0.0, -0.15, -0.55)),
}



LM_SIDE_R   = 234   # bordo guancia destra del soggetto
LM_SIDE_L   = 454   # bordo guancia sinistra del soggetto
LM_FOREHEAD = 10    # centro fronte
LM_NASION   = 168   # radice del naso, tra gli occhi


MIN_PAIR_DIST = 0.01

# Ampiezze tarate a mano su modello e webcam di riferimento.
AMPLITUDE   = 0.50   # moltiplicatore globale delle espressioni facciali (non la testa)
MOUTH_GAIN  = 0.60   # Jaw, Lip_Upper*, Lip_Lower*, Mouth_Corner_*
EYE_GAIN    = 1.00   # Eye_L/R, Eyelid_Up/Low_L/R
BROW_GAIN   = 0.75   # Brow_L/R
HEAD_GAIN   = 0.50   # traslazione e rotazione di Head
SMOOTHING   = 0.0   # alpha del filtro anti-jitter

CALIBRATION_FRAMES = 30
HEAD_DEPTH_GAIN = 1.0

MIN_FEATURE_SCALE = 0.35
MAX_FEATURE_SCALE = 4.0

MIN_LEVER_DOWN = 0.3

#apertura massima della mandibola in gradi
MAX_JAW_ANGLE = 40.0
