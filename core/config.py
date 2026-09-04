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


FACE_MAPPING = {nome: BoneMap(*riga) for nome, riga in _TABELLA.items()}

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
