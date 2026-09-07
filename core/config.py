from typing import NamedTuple


class BoneMap(NamedTuple):
    landmark: int         # indice MediaPipe che pilota l'osso
    parent_landmark: int  # landmark del genitore, None per la radice
    parent_bone: str      # nome dell'osso genitore, None per la radice
    position: tuple       # (x, y, z) normalizzati in [-1, 1] sulle semi-dimensioni
    gain: float           # ampiezza relativa dentro la sua feature
    scale_ref: tuple      # coppia di ossa che misura la feature, None = larghezza viso


_EYE_L = ("Eyelid_Up_L", "Eyelid_Low_L")    # apertura occhio sinistro
_EYE_R = ("Eyelid_Up_R", "Eyelid_Low_R")    # apertura occhio destro
_MOUTH = ("Mouth_Corner_L", "Mouth_Corner_R")   # larghezza bocca

_TABELLA = {
    "Head":           (1,   None, None,   (0.0,  0.0,  0.0),   1.0, None),
    # La mandibola e' pilotata in ROTAZIONE
    "Jaw":            (152, 1,    "Head", (0.0,  0.30, 0.05),  1.0, None),

    # centro dell'iride dell'occhio
    "Eye_L":          (473, 1,    "Head", (0.2, -0.2,  0.2),   1.0, None),
    "Eye_R":          (468, 1,    "Head", (-0.2, -0.2,  0.2),  1.0, None),

    # Palpebre
    "Eyelid_Up_L":    (386, 1,    "Head", (0.2, -0.22, 0.26),  1.15, _EYE_L),
    "Eyelid_Low_L":   (374, 1,    "Head", (0.2, -0.22, 0.14),  1.15, _EYE_L),
    "Eyelid_Up_R":    (159, 1,    "Head", (-0.2, -0.22, 0.26), 1.15, _EYE_R),
    "Eyelid_Low_R":   (145, 1,    "Head", (-0.2, -0.22, 0.14), 1.15, _EYE_R),

    "Brow_L":         (334, 1,    "Head", (0.2, -0.25, 0.4),   1.2, None),
    "Brow_R":         (105, 1,    "Head", (-0.2, -0.25, 0.4),  1.2, None),

    # Labbra: 5 punti di controllo per labbro (angolo, meta', centro, meta',
    # angolo).
    "Lip_Upper":      (0,   1,    "Head", (0.0, -0.2, -0.24),  0.7, _MOUTH),
    "Lip_Upper_L":    (269, 1,    "Head", (0.08, -0.18, -0.26), 0.7, _MOUTH),
    "Lip_Upper_R":    (39,  1,    "Head", (-0.08, -0.18, -0.26),0.7, _MOUTH),
    "Lip_Lower":      (17,  152,  "Jaw",  (0.0, -0.2, -0.36),  1.0, _MOUTH),
    "Lip_Lower_L":    (405, 152,  "Jaw",  (0.08, -0.18, -0.34), 1.0, _MOUTH),
    "Lip_Lower_R":    (181, 152,  "Jaw",  (-0.08, -0.18, -0.34),1.0, _MOUTH),

    "Mouth_Corner_L": (291, 152,  "Jaw",  (0.15, -0.15, -0.3), 1.0, _MOUTH),
    "Mouth_Corner_R": (61,  152,  "Jaw",  (-0.15, -0.15, -0.3),1.0, _MOUTH),
}
#landmark bones
#notes display these as 
_LANDMARKS_BONES_LUT = {
    ##################################################################
    #                              Lips                              #
    ##################################################################
    "LMK-Lip_corner.R":         (61,    None,   "LMK-Root",   (-0.033,  -0.063,     0.269),   1.0, None),
    "LMK-Lip_corner.L":         (291,   None,   "LMK-Root",   (0.033,   -0.063,     0.269),   1.0, None),
    "LMK-Lip_main_upp":         (0,     None,   "LMK-Root",   (0.0,     -0.085,     0.282),  1.0, None),
    "LMK-Lip_upp1.R":           (37,    None,   "LMK-Root",   (-0.011,   -0.085,     0.281),  1.0, None),
    "LMK-Lip_upp2.R":           (39,    None,   "LMK-Root",   (-0.019,   -0.078,     0.279),  1.0, None),
    "LMK-Lip_upp1.L":           (267,   None,   "LMK-Root",   (0.011,   -0.085,     0.281),  1.0, None),
    "LMK-Lip_upp2.L":           (269,   None,   "LMK-Root",   (0.019,   -0.078,     0.279),  1.0, None),
    
    "LMK-Lip_main_low":         (17,    None,    "LMK-Root", (0.0,    -0.078,   0.257),  1.0, None),
    "LMK-Lip_low1.R":           (84,    None,    "LMK-Root", (-0.012,  -0.076, 0.257),  1.0, None),
    "LMK-Lip_low2.R":           (181,   None,    "LMK-Root", (-0.020,  -0.072, 0.257),  1.0, None),
    "LMK-Lip_low1.L":           (314,   None,    "LMK-Root", (0.012,  -0.076, 0.257),  1.0, None),
    "LMK-Lip_low2.L":           (405,   None,    "LMK-Root", (0.020,  -0.072, 0.257),  1.0, None),

    ##################################################################
    #                              Eye                               #
    ##################################################################
    "LMK-Eye.L":          (474, None,    "LMK-Root",  (0.049,    -0.133,  0.378),   1.0, None),
    "LMK-Eye.R":          (469, None,    "LMK-Root",  (-0.049,   -0.133,  0.378),  1.0, None),

    ##################################################################
    #                            Eyelid                              #
    ##################################################################
    "LMR-Eyelid_corner_in.L":   (398, None,    "LMK-Root", (0.025, -0.048, 0.372),  1.0, None),
    "LMR-Eyelid_upp1.L":        (384, None,    "LMK-Root", (0.039, -0.051, 0.382),  1.0, None),
    "LMR-Eyelid_upp2.L":        (386, None,    "LMK-Root", (0.052, -0.054, 0.384),  1.0, None),
    "LMR-Eyelid_upp3.L":        (388, None,    "LMK-Root", (0.067, -0.047, 0.382),  1.0, None),
    "LMR-Eyelid_corner_out.L":  (263, None,    "LMK-Root", (0.073, -0.035, 0.378),  1.0, None),
    "LMR-Eyelid_low1.L":        (381, None,    "LMK-Root", (0.040, -0.049, 0.372),  1.0, None),
    "LMR-Eyelid_low2.L":        (374, None,    "LMK-Root", (0.053, -0.050, 0.370),  1.0, None),
    "LMR-Eyelid_low3.L":        (390, None,    "LMK-Root", (0.066, -0.040, 0.374),  1.0, None),

    "LMR-Eyelid_corner_in.R":   (133, None,    "LMK-Root", (-0.025, -0.048, 0.372),  1.0, None),
    "LMR-Eyelid_upp1.R":        (157, None,    "LMK-Root", (-0.039, -0.051, 0.382),  1.0, None),
    "LMR-Eyelid_upp2.R":        (159, None,    "LMK-Root", (-0.052, -0.054, 0.384),  1.0, None),
    "LMR-Eyelid_upp3.R":        (161, None,    "LMK-Root", (-0.067, -0.047, 0.382),  1.0, None),
    "LMR-Eyelid_corner_out.R":  (33,  None,    "LMK-Root", (-0.073, -0.035, 0.378),  1.0, None),
    "LMR-Eyelid_low1.R":        (154, None,    "LMK-Root", (-0.040, -0.049, 0.372),  1.0, None),
    "LMR-Eyelid_low2.R":        (145, None,    "LMK-Root", (-0.053, -0.050, 0.370),  1.0, None),
    "LMR-Eyelid_low3.R":        (163, None,    "LMK-Root", (-0.066, -0.040, 0.374),  1.0, None),
    
    ##################################################################
    #                              BROW                              #
    ##################################################################
    "LMR-Brow1.L":         (336, None,    "LMK-Root", (0.039, -0.078, 0.418),   1.0, None),
    "LMR-Brow2.L":         (334, None,    "LMK-Root", (0.077, -0.056, 0.420),   1.0, None),
    "LMR-Brow3.L":         (300, None,    "LMK-Root", (0.098, -0.018, 0.408),   1.0, None),
    "LMR-Brow1.R":         (107, None,    "LMK-Root", (-0.039, -0.078, 0.418),  1.0, None),
    "LMR-Brow2.R":         (105, None,    "LMK-Root", (-0.077, -0.056, 0.420),  1.0, None),
    "LMR-Brow3.R":         (70,  None,    "LMK-Root", (-0.098, -0.018, 0.408),  1.0, None),
    
    ##################################################################
    #                            FACE OVAL                           #
    ##################################################################
    "LMR-Face_oval1.L":         (338, None,    "LMK-Root", (0.038, -0.063, 0.472),   1.0, None),
    "LMR-Face_oval2.L":         (332, None,    "LMK-Root", (0.082, -0.035, 0.461),   1.0, None),
    "LMR-Face_oval3.L":         (454, None,    "LMK-Root", (0.11, 0.054, 0.36),   1.0, None),
    "LMR-Face_oval4.L":         (361, None,    "LMK-Root", (0.106, 0.061, 0.316),   1.0, None),
    "LMR-Face_oval5.L":         (379, None,    "LMK-Root", (0.057, -0.016, 0.233),   1.0, None),
    
    "LMR-Face_oval_chin":       (152, None,    "LMK-Root", (0.0, -0.056, 0.206),   1.0, None),
    
    "LMR-Face_oval1.R":         (109, None,    "LMK-Root", (-0.038, -0.063, 0.472),   1.0, None),
    "LMR-Face_oval2.R":         (103, None,    "LMK-Root", (-0.082, -0.035, 0.461),   1.0, None),
    "LMR-Face_oval3.R":         (234, None,    "LMK-Root", (-0.11, 0.054, 0.36),   1.0, None),
    "LMR-Face_oval4.R":         (132, None,    "LMK-Root", (-0.106, 0.061, 0.316),   1.0, None),
    "LMR-Face_oval5.R":         (150, None,    "LMK-Root", (-0.057, -0.016, 0.233),   1.0, None),
    ##################################################################
    #                            NOSE                                #
    ##################################################################
    "LMR-Nose_tip":          (4,    None,    "LMK-Root", (0.0, -0.112, 0.314),   1.0, None),
    "LMR-Nose_base":         (168,  None,    "LMK-Root", (0.0, -0.083, 0.381),   1.0, None),
    "LMR-Nostril.L":         (358,  None,    "LMK-Root", (0.031, -0.069, 0.311),   1.0, None),
    "LMR-Nostril.R":         (129,  None,    "LMK-Root", (-0.031, -0.069, 0.311),   1.0, None),

    ##################################################################
    #                            CHEEK                               #
    ##################################################################
    "LMR-Cheek_upp.L":          (280, None,    "LMK-Root", (0.078, -0.043, 0.339),   1.0, None),
    "LMR-Cheek_low.L":          (426, None,    "LMK-Root", (0.054, -0.056, 0.290),   1.0, None),
    "LMR-Cheek_in.L":           (266, None,    "LMK-Root", (0.044, -0.062, 0.329),   1.0, None),
    "LMR-Cheek_out.L":          (416, None,    "LMK-Root", (0.079, -0.021, 0.284),   1.0, None),

    "LMR-Cheek_upp.R":          (50,    None,    "LMK-Root", (-0.078, -0.043, 0.339),   1.0, None),
    "LMR-Cheek_low.R":          (206,   None,    "LMK-Root", (-0.054, -0.056, 0.290),   1.0, None),
    "LMR-Cheek_in.R":           (36,    None,    "LMK-Root", (-0.044, -0.062, 0.329),   1.0, None),
    "LMR-Cheek_out.R":          (192,   None,    "LMK-Root", (-0.079, -0.021, 0.284),   1.0, None),

}

_RIG_BONES_LUT = {
    "Head":           (1,   None, None,   (0.0,  0.0,  0.0),   1.0, None),
    # La mandibola e' pilotata in ROTAZIONE
    "Jaw":            (152, 1,    "Head", (0.0,  0.30, 0.05),  1.0, None),

    # centro dell'iride dell'occhio
    "Eye_L":          (473, 1,    "Head", (0.2, -0.2,  0.2),   1.0, None),
    "Eye_R":          (468, 1,    "Head", (-0.2, -0.2,  0.2),  1.0, None),

    # Palpebre
    "Eyelid_Up_L":    (386, 1,    "Head", (0.2, -0.22, 0.26),  1.15, _EYE_L),
    "Eyelid_Low_L":   (374, 1,    "Head", (0.2, -0.22, 0.14),  1.15, _EYE_L),
    "Eyelid_Up_R":    (159, 1,    "Head", (-0.2, -0.22, 0.26), 1.15, _EYE_R),
    "Eyelid_Low_R":   (145, 1,    "Head", (-0.2, -0.22, 0.14), 1.15, _EYE_R),

    "Brow_L":         (334, 1,    "Head", (0.2, -0.25, 0.4),   1.2, None),
    "Brow_R":         (105, 1,    "Head", (-0.2, -0.25, 0.4),  1.2, None),

    # Labbra: 5 punti di controllo per labbro (angolo, meta', centro, meta',
    # angolo).
    "Lip_Upper":      (0,   1,    "Head", (0.0, -0.2, -0.24),  0.7, _MOUTH),
    "Lip_Upper_L":    (269, 1,    "Head", (0.08, -0.18, -0.26), 0.7, _MOUTH),
    "Lip_Upper_R":    (39,  1,    "Head", (-0.08, -0.18, -0.26),0.7, _MOUTH),
    "Lip_Lower":      (17,  152,  "Jaw",  (0.0, -0.2, -0.36),  1.0, _MOUTH),
    "Lip_Lower_L":    (405, 152,  "Jaw",  (0.08, -0.18, -0.34), 1.0, _MOUTH),
    "Lip_Lower_R":    (181, 152,  "Jaw",  (-0.08, -0.18, -0.34),1.0, _MOUTH),

    "Mouth_Corner_L": (291, 152,  "Jaw",  (0.15, -0.15, -0.3), 1.0, _MOUTH),
    "Mouth_Corner_R": (61,  152,  "Jaw",  (-0.15, -0.15, -0.3),1.0, _MOUTH),
    ##################################################################
    #                      Deformation bones                         #
    ##################################################################

    #to add new and deformation bones (set the color to red: PoseMode->ViewportDisplay->BoneColor,PoseMode->ViewportDisplay->PoseBoneColor)
    #Display these bone as BBone and scale them
    #Initial bones:
    #Neck bone, name: DEF-Neck1 at the base of the neck and laryngeal prominence
    #Neck2 bone, name: DEF-Neck2 from laryngeal prominance to the base of jaw
    #Head bone, name: DEF-Head
    #Jaw bone, name: DEF-Jaw at the base of ears
    #chin bone, name: DEF-Chin
    #jawline, name: DEF-Jawline1.L->Symetrize at the center of the jawline
    #Nose:
    #Nose bone, name: DEF-Nose at the base of the nose
    #Nose tip bone, name: DEF-Nose_tip at the tip of the nose
    #Nose bone bridge, name: DEF-Nose_bridge at the bridge of the nose
    #Nostril bone, name: DEF-Nostril.L at the nostril of the nose ->symetrize
    #Lips:
    #create all the bones for the lips following the structure of the 
    #stretch bones
    ##################################################################
    #                      Master bones                              #
    ##################################################################
    
    #Master bones (set the color to blue: PoseMode->ViewportDisplay->BoneColor,PoseMode->ViewportDisplay->PoseBoneColor)
    #jawline, name: MSTR-Jawline.L -> at the center between the three jawline def bones
    ##################################################################
    #                      Control bones                             #
    ##################################################################
    
    #Control bones (set the color to yellow: PoseMode->ViewportDisplay->BoneColor,PoseMode->ViewportDisplay->PoseBoneColor)
    #Lips
    #for the mouth a ribbon mesh helper approach to obtain good weight should be used
    #CLT-Lip_main_upp place it on the upper center of the lip loop
    #CLT-Lip_main_low place it on the upper center of the lip loop
    #CLT-Lip_corn.L place it on the left corner of the lip loop ->symmetrize
    #CLT-Lip_local_low

    ##################################################################
    #                      Stretch bones                             #
    ##################################################################
    #To valuate if add them for the lips control 
    
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


MIN_PAIR_DIST = 0.05

# Ampiezze tarate a mano su modello e webcam di riferimento.
AMPLITUDE   = 0.50   # moltiplicatore globale delle espressioni facciali (non la testa)
MOUTH_GAIN  = 0.60   # Jaw, Lip_Upper*, Lip_Lower*, Mouth_Corner_*
EYE_GAIN    = 1.00   # Eye_L/R, Eyelid_Up/Low_L/R
BROW_GAIN   = 0.75   # Brow_L/R
HEAD_GAIN   = 0.50   # traslazione e rotazione di Head
SMOOTHING   = 0.70   # alpha del filtro anti-jitter

CALIBRATION_FRAMES = 30
HEAD_DEPTH_GAIN = 1.0

MIN_FEATURE_SCALE = 0.35
MAX_FEATURE_SCALE = 4.0

MIN_LEVER_DOWN = 0.3

#apertura massima della mandibola in gradi
MAX_JAW_ANGLE = 40.0
