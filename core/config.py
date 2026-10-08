from enum import Enum
from typing import NamedTuple
from dataclasses import dataclass
from mathutils import Vector, Quaternion

class MotionMode(Enum):
    HEAD = "HEAD"
    LANDMARK = "LANDMARK"
    RELATIVE = "RELATIVE"
    TRANSLATION = "TRANSLATION"
    ROTATION = "ROTATION"
    AIM = "AIM"

@dataclass
class LandmarkSample:
    idx: int
    pos: Vector
    neutral_pos: Vector
    delta: Vector

@dataclass(frozen=True)
class LandmarkBoneMap:
    bone: str
    id_landmark: int
    parent_landmark: int | None
    parent_bone: str | None
    rest_position: tuple[float, float, float]
    gaint: float = 1.0
    rot_axis: tuple[float, float, float] | None = None
    motion_mode: MotionMode = MotionMode.LANDMARK
    rot_landmarks: tuple[int, ...] = ()

#data structure for the mapping in runtime
@dataclass(frozen=True)
class MappingRuntime:
    role: str
    source: tuple[str, ...]
    target_bone: str
    mode: MotionMode
    gain: float = 1.0
    enable: bool = True
    axis_mask: tuple[bool, bool, bool] = (True, True, True)
    
#data structure that allows us to create a mapping between the source skeleton 
# and the target skeleton
@dataclass(frozen=True)
class RetargetMap:
    source: tuple[str, ...]
    target: str
    mode: MotionMode
    gain: float = 1.0
    enable: bool = True
    axis_mask: tuple[bool, bool, bool] = (True, True, True)

#Target rig
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

#mapping between landmarks and target bones 
#the dir key is the role 
DEFAULT_RETARGET_MAP = {
    #to see the source LMK
    #Neck e Head ricevono la stessa rotazione della testa: il gain e' la frazione
    #dell'angolo che va a ciascun osso. Se DEF-Head e' figlio di DEF-Neck2 la
    #rotazione totale e' la somma dei due gain (0.4 + 0.6 = 1); se non lo e',
    #mettere Neck a 0 e Head a 1.
    "Neck": RetargetMap(source=("LMK-Face_oval3.R", "LMK-Face_oval3.L", "LMK-Face_oval1.L"),
                target="DEF-Neck2",
                mode=MotionMode.ROTATION,
                gain=0.4),
    "Head": RetargetMap(source=("LMK-Face_oval3.R", "LMK-Face_oval3.L", "LMK-Face_oval1.L"),
                    target="DEF-Head",
                    mode=MotionMode.ROTATION,
                    gain=0.6),
    "Jaw": RetargetMap(source=("LMK-Face_oval4.R", "LMK-Face_oval4.L", "LMK-Face_oval_chin"),
                    target="DEF-Jaw",
                    mode=MotionMode.ROTATION),
    #Nostril
    "Nostril L": RetargetMap(source=("LMK-Nostril.L",),
                    target="DEF-Nostril.L",
                    mode=MotionMode.TRANSLATION),
    "Nostril R": RetargetMap(source=("LMK-Nostril.R",),
                        target="DEF-Nostril.R",
                        mode=MotionMode.TRANSLATION),
    #Lips, to see the source LMK
    "Lip local upp": RetargetMap(source=("LMK-Lip_main_upp",),
                    target="CTL-Lip_local_upp",
                    mode=MotionMode.TRANSLATION,
                    gain=1),
    "Lip local upp L": RetargetMap(source=("LMK-Lip_upp2.L",),
                    target="CTL-Lip_local_upp.L",
                    mode=MotionMode.TRANSLATION,
                    gain=1),
    "Lip local upp R": RetargetMap(source=("LMK-Lip_upp2.R",),
                    target="CTL-Lip_local_upp.R",
                    mode=MotionMode.TRANSLATION,
                    gain=1),
    "Lip local low": RetargetMap(source=("LMK-Lip_main_low",),
                        target="CTL-Lip_local_low",
                        mode=MotionMode.TRANSLATION,
                        gain=1),
    "Lip local low L": RetargetMap(source=("LMK-Lip_low2.L",),
                        target="CTL-Lip_local_low.L",
                        mode=MotionMode.TRANSLATION,
                        gain=1),
    "Lip local low R": RetargetMap(source=("LMK-Lip_low2.R",),
                        target="CTL-Lip_local_low.R",
                        mode=MotionMode.TRANSLATION,
                        gain=1),
    "Lip corner L": RetargetMap(source=("LMK-Lip_corner.L",),
                            target="CTL-Lip_corn.L",
                            mode=MotionMode.TRANSLATION,
                            gain=1),
    "Lip corner R": RetargetMap(source=("LMK-Lip_corner.R",),
                                target="CTL-Lip_corn.R",
                                mode=MotionMode.TRANSLATION,
                                gain=1),
    #Brow, to see the source LMK
    "Brow inner L": RetargetMap(source=("LMK-Brow1.L",),
                                target="CTL-Brow_in.L",
                                mode=MotionMode.TRANSLATION,
                                gain=1.5),
    "Brow middle L": RetargetMap(source=("LMK-Brow2.L",),
                                target="CTL-Brow_mid.L",
                                mode=MotionMode.TRANSLATION,
                                gain=1.5),
    "Brow outer L": RetargetMap(source=("LMK-Brow3.L",),
                                target="CTL-Brow_out.L",
                                mode=MotionMode.TRANSLATION,
                                gain=1.5),
    "Brow inner R": RetargetMap(source=("LMK-Brow1.R",),
                                    target="CTL-Brow_in.R",
                                    mode=MotionMode.TRANSLATION,
                                    gain=1.5),
    "Brow middle R": RetargetMap(source=("LMK-Brow2.R",),
                                    target="CTL-Brow_mid.R",
                                    mode=MotionMode.TRANSLATION,
                                    gain=1.5),
    "Brow outer R": RetargetMap(source=("LMK-Brow3.R",),
                                    target="CTL-Brow_out.R",
                                    mode=MotionMode.TRANSLATION,
                                    gain=1.5),
    #Eye, to see the source LMK
    "Eye L": RetargetMap(source=("LMK-Eye.L",),
                                    target="TGT-Eye.L",
                                    mode=MotionMode.TRANSLATION),
    "Eye R": RetargetMap(source=("LMK-Eye.R",),
                                    target="TGT-Eye.R",
                                    mode=MotionMode.TRANSLATION),
    #Eyelid, to see the source LMK
    "Eyelid upper L": RetargetMap(source=("LMK-Eyelid_upp2.L",),
                                        target="P-Eyelid_upp.L",
                                        mode=MotionMode.TRANSLATION,
                                        gain=1.2),
    "Eyelid upper R": RetargetMap(source=("LMK-Eyelid_upp2.R",),
                                        target="P-Eyelid_upp.R",
                                        mode=MotionMode.TRANSLATION,
                                        gain=1.3),
    "Eyelid lower L": RetargetMap(source=("LMK-Eyelid_low2.L",),
                                            target="P-Eyelid_low.L",
                                            mode=MotionMode.TRANSLATION,
                                            gain=1.2),
    "Eyelid lower R": RetargetMap(source=("LMK-Eyelid_low2.R",),
                                            target="P-Eyelid_low.R",
                                            mode=MotionMode.TRANSLATION,
                                            gain=1.3),
}

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

# position = dove sta il landmark sul modello (l'ancora usata dal solver), in
# coordinate normalizzate [-1, 1] sulle semi-dimensioni della mesh, con
# l'origine nel centro del bbox alzato di GENERATOR_Z_OFFSET (vedi
# "Genera Armatura su Modello"). Ricavate da FaceMocap_Rig, posizionato a mano
# sul modello di riferimento e reso simmetrico.
_TABELLA = {
    # ancora sulla punta del naso (landmark 1): stimata, il naso e' il punto
    # piu' avanzato del bbox; la geometria dell'osso e' in BONE_SHAPES
    "Head":           (1,   None, None,   (0.0, -1.0, -0.42),      1.0, None, MotionMode.HEAD),
    # La mandibola e' pilotata in ROTAZIONE: ancora sul mento (coda dell'osso)
    "Jaw":            (152, 1,    "Head", (0.0, -0.72, -0.875),    1.0, None, MotionMode.RELATIVE),

    # centro dell'iride dell'occhio
    "Eye.L":          (473, 1,    "Head", (0.376, -0.599, -0.158), 1.0, None, MotionMode.RELATIVE),
    "Eye.R":          (468, 1,    "Head", (-0.376, -0.599, -0.158), 1.0, None, MotionMode.RELATIVE),

    # Palpebre
    "Eyelid_Up.L":    (386, 1,    "Head", (0.382, -0.638, -0.118),  1.15, _EYE_L, MotionMode.RELATIVE),
    "Eyelid_Low.L":   (374, 1,    "Head", (0.373, -0.649, -0.188),  1.15, _EYE_L, MotionMode.RELATIVE),
    "Eyelid_Up.R":    (159, 1,    "Head", (-0.382, -0.638, -0.118), 1.15, _EYE_R, MotionMode.RELATIVE),
    "Eyelid_Low.R":   (145, 1,    "Head", (-0.373, -0.649, -0.188), 1.15, _EYE_R, MotionMode.RELATIVE),

    "Brow.L":         (334, 1,    "Head", (0.427, -0.638, -0.066),  1.2, None, MotionMode.RELATIVE),
    "Brow.R":         (105, 1,    "Head", (-0.427, -0.638, -0.066), 1.2, None, MotionMode.RELATIVE),

    # Labbra: 5 punti di controllo per labbro (angolo, meta', centro, meta',
    # angolo).
    "Lip_Upper":      (0,   1,    "Head", (0.0, -0.789, -0.601),    0.7, _MOUTH, MotionMode.RELATIVE),
    "Lip_Upper.L":    (269, 1,    "Head", (0.163, -0.776, -0.596),  0.7, _MOUTH, MotionMode.RELATIVE),
    "Lip_Upper.R":    (39,  1,    "Head", (-0.163, -0.776, -0.596), 0.7, _MOUTH, MotionMode.RELATIVE),
    "Lip_Lower":      (17,  152,  "Jaw",  (0.0, -0.806, -0.674),    1.0, _MOUTH, MotionMode.RELATIVE),
    "Lip_Lower.L":    (405, 152,  "Jaw",  (0.146, -0.762, -0.669),  1.0, _MOUTH, MotionMode.RELATIVE),
    "Lip_Lower.R":    (181, 152,  "Jaw",  (-0.146, -0.762, -0.669), 1.0, _MOUTH, MotionMode.RELATIVE),

    "Mouth_Corner.L": (291, 152,  "Jaw",  (0.28, -0.693, -0.626),   1.0, _MOUTH, MotionMode.RELATIVE),
    "Mouth_Corner.R": (61,  152,  "Jaw",  (-0.28, -0.693, -0.626),  1.0, _MOUTH, MotionMode.RELATIVE),
}

# Geometria (testa, coda) delle ossa generate, stesse coordinate di _TABELLA.
# Le code corte e rivolte dentro il volume danno pesi locali al bone heat.
# Head va dalla base del collo alla cima del cranio, Jaw dal perno al mento.
BONE_SHAPES = {
    "Head":           ((0.0, 0.2, -1.2),        (0.0, 0.2, 0.4)),
    "Jaw":            ((0.0, 0.16, -0.298),     (0.0, -0.72, -0.875)),
    "Eye.L":          ((0.376, -0.599, -0.158), (0.334, -0.538, -0.146)),
    "Eye.R":          ((-0.376, -0.599, -0.158), (-0.334, -0.538, -0.146)),
    "Eyelid_Up.L":    ((0.382, -0.638, -0.118), (0.403, -0.658, -0.065)),
    "Eyelid_Up.R":    ((-0.382, -0.638, -0.118), (-0.403, -0.658, -0.065)),
    "Eyelid_Low.L":   ((0.373, -0.649, -0.188), (0.35, -0.582, -0.2)),
    "Eyelid_Low.R":   ((-0.373, -0.649, -0.188), (-0.35, -0.582, -0.2)),
    "Brow.L":         ((0.427, -0.638, -0.066), (0.405, -0.583, -0.1)),
    "Brow.R":         ((-0.427, -0.638, -0.066), (-0.405, -0.583, -0.1)),
    "Lip_Upper":      ((0.0, -0.789, -0.601),   (0.0, -0.788, -0.543)),
    "Lip_Upper.L":    ((0.163, -0.776, -0.596), (0.113, -0.72, -0.585)),
    "Lip_Upper.R":    ((-0.163, -0.776, -0.596), (-0.113, -0.72, -0.585)),
    "Lip_Lower":      ((0.0, -0.806, -0.674),   (0.0, -0.736, -0.665)),
    "Lip_Lower.L":    ((0.146, -0.762, -0.669), (0.11, -0.699, -0.657)),
    "Lip_Lower.R":    ((-0.146, -0.762, -0.669), (-0.11, -0.699, -0.657)),
    "Mouth_Corner.L": ((0.28, -0.693, -0.626),  (0.302, -0.654, -0.647)),
    "Mouth_Corner.R": ((-0.28, -0.693, -0.626), (-0.302, -0.654, -0.647)),
}

# Ossa che non deformano la mesh: gli occhi sono pilotati in traslazione
# dall'iride, se deformassero la pelle lo sguardo trascinerebbe la palpebra.
NON_DEFORM_BONES = {"Eye.L", "Eye.R"}

# Il generatore centra l'armatura nel bbox della mesh alzato di questa
# frazione dell'altezza: la cima della mesh sta a z = 1 - 2 * offset.
GENERATOR_Z_OFFSET = 0.15

# Modelli con collo (core/head_measure.py): il template si normalizza sulla
# testa misurata invece che sul bbox, che con collo e spalle e' dominato dal busto.
# Profondita'/larghezza del bbox del modello di riferimento: sul template la
# scala in Y e' questa frazione di quella in X.
GENERATOR_REF_ASPECT_YX = 0.97
# Mento = prima quota sotto il naso dove il bordo anteriore arretra di almeno
# questa frazione della larghezza della testa. Labbra e mento restano entro
# ~0.15, la gola sta oltre ~0.45.
GENERATOR_CHIN_RECESS = 0.30
# Collo riconosciuto se sotto il mento c'e' almeno questa frazione dell'altezza
# della testa (mento -> cima). Il modello di riferimento ne ha ~0.27.
GENERATOR_MIN_NECK = 0.35
# Sfumatura dei pesi di Neck e Chest dopo il collegamento: sopra il mento
# valgono zero, e tornano pieni a questa frazione dell'altezza della testa
# sotto il mento. Senza, il bone heat da' al collo parte di labbra e mento, che
# allora seguono la mandibola solo in parte.
BODY_WEIGHT_FADE = 0.10
# Altezza delle fasce del profilo, in frazione dell'altezza della mesh.
GENERATOR_BAND = 0.02
# Base del collo: la prima fascia sotto la strozzatura larga questo multiplo di essa.
GENERATOR_NECK_FLARE = 1.3
# Head quando c'e' il collo, nelle coordinate di BONE_SHAPES: dalla base del
# cranio in su, invece che dal fondo del bbox.
NECK_HEAD_SHAPE = ((0.0, 0.4, -0.6), (0.0, 0.2, 0.4))
# Frazione della rotazione della testa data a Neck. Head e' suo figlio e prende
# il resto, quindi la rotazione totale non cambia: cambia dove si piega.
NECK_ROT_SHARE = 0.4
# Frazione data a Chest, la radice: fa seguire la testa anche al collo basso e
# all'inizio delle spalle. Head prende 1 - CHEST - NECK.
CHEST_ROT_SHARE = 0.15
# Ossa del corpo create sui modelli con collo. Il tracking le muove solo in
# rotazione (le quote qui sopra) e Ripara Armatura non le tocca.
BODY_BONES = ("Chest", "Neck")

#landmark mapping (source skeleton)
LANDMARKS_MAP = {
    ##################################################################
    #                              Lips                              #
    ##################################################################
    "LMK-Lip_corner.R":         LandmarkBoneMap(bone="LMK-Lip_corner.R",    id_landmark=61,    parent_landmark=None,   parent_bone="LMK-Root",   rest_position=(-0.033,  -0.063,     0.269),     motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_corner.L":         LandmarkBoneMap(bone="LMK-Lip_corner.L",    id_landmark=291,   parent_landmark=None,   parent_bone="LMK-Root",   rest_position=(0.033,   -0.063,     0.269),     motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_main_upp":         LandmarkBoneMap(bone="LMK-Lip_main_upp",    id_landmark=0,     parent_landmark=None,   parent_bone="LMK-Root",   rest_position=(0.0,     -0.085,     0.282),     motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_upp1.R":           LandmarkBoneMap(bone="LMK-Lip_upp1.R",      id_landmark=37,    parent_landmark=None,   parent_bone="LMK-Root",   rest_position=(-0.011,   -0.085,     0.281),    motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_upp2.R":           LandmarkBoneMap(bone="LMK-Lip_upp2.R",      id_landmark=39,    parent_landmark=None,   parent_bone="LMK-Root",   rest_position=(-0.019,   -0.078,     0.279),    motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_upp1.L":           LandmarkBoneMap(bone="LMK-Lip_upp1.L",      id_landmark=267,   parent_landmark=None,   parent_bone="LMK-Root",   rest_position=(0.011,   -0.085,     0.281),     motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_upp2.L":           LandmarkBoneMap(bone="LMK-Lip_upp2.L",      id_landmark=269,   parent_landmark=None,   parent_bone="LMK-Root",   rest_position=(0.019,   -0.078,     0.279),     motion_mode=MotionMode.LANDMARK),
    
    "LMK-Lip_main_low":         LandmarkBoneMap(bone="LMK-Lip_main_low",     id_landmark=17,    parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.0,    -0.078,   0.257), motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_low1.R":           LandmarkBoneMap(bone="LMK-Lip_low1.R",       id_landmark=84,    parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.012,  -0.076, 0.257),  motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_low2.R":           LandmarkBoneMap(bone="LMK-Lip_low2.R",       id_landmark=181,   parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.020,  -0.072, 0.257),  motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_low1.L":           LandmarkBoneMap(bone="LMK-Lip_low1.L",       id_landmark=314,   parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.012,  -0.076, 0.257),   motion_mode=MotionMode.LANDMARK),
    "LMK-Lip_low2.L":           LandmarkBoneMap(bone="LMK-Lip_low2.L",       id_landmark=405,   parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.020,  -0.072, 0.257),   motion_mode=MotionMode.LANDMARK),

    ##################################################################
    #                              Eye                               #
    ##################################################################
    "LMK-Eye.L":          LandmarkBoneMap(bone="LMK-Eye.L", id_landmark=474, parent_landmark=None,    parent_bone="LMK-Root",  rest_position=(0.049,    -0.133,  0.378), motion_mode=MotionMode.LANDMARK),
    "LMK-Eye.R":          LandmarkBoneMap(bone="LMK-Eye.R", id_landmark=469, parent_landmark=None,    parent_bone="LMK-Root",  rest_position=(-0.049,   -0.133,  0.378), motion_mode=MotionMode.LANDMARK),

    ##################################################################
    #                            Eyelid                              #
    ##################################################################
    "LMK-Eyelid_corner_in.L":   LandmarkBoneMap(bone="LMK-Eyelid_corner_in.L",   id_landmark=398, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.025, -0.048, 0.372), motion_mode=MotionMode.LANDMARK),
    "LMK-Eyelid_upp1.L":        LandmarkBoneMap(bone="LMK-Eyelid_upp1.L",        id_landmark=384, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.039, -0.051, 0.382), motion_mode=MotionMode.LANDMARK),
    "LMK-Eyelid_upp2.L":        LandmarkBoneMap(bone="LMK-Eyelid_upp2.L",        id_landmark=386, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.052, -0.054, 0.384), motion_mode=MotionMode.LANDMARK),
    "LMK-Eyelid_upp3.L":        LandmarkBoneMap(bone="LMK-Eyelid_upp3.L",        id_landmark=388, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.067, -0.047, 0.382), motion_mode=MotionMode.LANDMARK),
    "LMK-Eyelid_corner_out.L":  LandmarkBoneMap(bone="LMK-Eyelid_corner_out.L",  id_landmark=263, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.073, -0.035, 0.378), motion_mode=MotionMode.LANDMARK),
    "LMK-Eyelid_low1.L":        LandmarkBoneMap(bone="LMK-Eyelid_low1.L",        id_landmark=381, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.040, -0.049, 0.372), motion_mode=MotionMode.LANDMARK),
    "LMK-Eyelid_low2.L":        LandmarkBoneMap(bone="LMK-Eyelid_low2.L",        id_landmark=374, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.053, -0.050, 0.370), motion_mode=MotionMode.LANDMARK),
    "LMK-Eyelid_low3.L":        LandmarkBoneMap(bone="LMK-Eyelid_low3.L",        id_landmark=390, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.066, -0.040, 0.374), motion_mode=MotionMode.LANDMARK),

    "LMK-Eyelid_corner_in.R":   LandmarkBoneMap(bone="LMK-Eyelid_corner_in.R",   id_landmark=133, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.025, -0.048, 0.372), motion_mode=MotionMode.LANDMARK),
    "LMK-Eyelid_upp1.R":        LandmarkBoneMap(bone="LMK-Eyelid_upp1.R",        id_landmark=157, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.039, -0.051, 0.382), motion_mode=MotionMode.LANDMARK),
    "LMK-Eyelid_upp2.R":        LandmarkBoneMap(bone="LMK-Eyelid_upp2.R",        id_landmark=159, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.052, -0.054, 0.384), motion_mode=MotionMode.LANDMARK),
    "LMK-Eyelid_upp3.R":        LandmarkBoneMap(bone="LMK-Eyelid_upp3.R",        id_landmark=161, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.067, -0.047, 0.382), motion_mode=MotionMode.LANDMARK),
    "LMK-Eyelid_corner_out.R":  LandmarkBoneMap(bone="LMK-Eyelid_corner_out.R",  id_landmark=33,  parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.073, -0.035, 0.378), motion_mode=MotionMode.LANDMARK),
    "LMK-Eyelid_low1.R":        LandmarkBoneMap(bone="LMK-Eyelid_low1.R",        id_landmark=154, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.040, -0.049, 0.372), motion_mode=MotionMode.LANDMARK),
    "LMK-Eyelid_low2.R":        LandmarkBoneMap(bone="LMK-Eyelid_low2.R",        id_landmark=145, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.053, -0.050, 0.370), motion_mode=MotionMode.LANDMARK),
    "LMK-Eyelid_low3.R":        LandmarkBoneMap(bone="LMK-Eyelid_low3.R",        id_landmark=163, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.066, -0.040, 0.374), motion_mode=MotionMode.LANDMARK),
    
    ##################################################################
    #                              BROW                              #
    ##################################################################
    "LMK-Brow1.L":         LandmarkBoneMap(bone="LMK-Brow1.L",   id_landmark=336, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.039, -0.078, 0.418),   motion_mode=MotionMode.LANDMARK),
    "LMK-Brow2.L":         LandmarkBoneMap(bone="LMK-Brow2.L",   id_landmark=334, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.077, -0.056, 0.420),   motion_mode=MotionMode.LANDMARK),
    "LMK-Brow3.L":         LandmarkBoneMap(bone="LMK-Brow3.L",   id_landmark=300, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.098, -0.018, 0.408),   motion_mode=MotionMode.LANDMARK),
    "LMK-Brow1.R":         LandmarkBoneMap(bone="LMK-Brow1.R",   id_landmark=107, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.039, -0.078, 0.418),  motion_mode=MotionMode.LANDMARK),
    "LMK-Brow2.R":         LandmarkBoneMap(bone="LMK-Brow2.R",   id_landmark=105, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.077, -0.056, 0.420),  motion_mode=MotionMode.LANDMARK),
    "LMK-Brow3.R":         LandmarkBoneMap(bone="LMK-Brow3.R",   id_landmark=70,  parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.098, -0.018, 0.408),  motion_mode=MotionMode.LANDMARK),
    
    ##################################################################
    #                            FACE OVAL                           #
    ##################################################################
    "LMK-Face_oval1.L":         LandmarkBoneMap(bone="LMK-Face_oval1.L", id_landmark=338, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.038, -0.063, 0.472),      motion_mode=MotionMode.LANDMARK),
    "LMK-Face_oval2.L":         LandmarkBoneMap(bone="LMK-Face_oval2.L", id_landmark=332, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.082, -0.035, 0.461),      motion_mode=MotionMode.LANDMARK),
    "LMK-Face_oval3.L":         LandmarkBoneMap(bone="LMK-Face_oval3.L", id_landmark=454, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.11, 0.054, 0.36),         motion_mode=MotionMode.LANDMARK),
    "LMK-Face_oval4.L":         LandmarkBoneMap(bone="LMK-Face_oval4.L", id_landmark=361, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.106, 0.061, 0.316),       motion_mode=MotionMode.LANDMARK),
    "LMK-Face_oval5.L":         LandmarkBoneMap(bone="LMK-Face_oval5.L", id_landmark=379, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.057, -0.016, 0.233),      motion_mode=MotionMode.LANDMARK),
    
    "LMK-Face_oval_chin":       LandmarkBoneMap(bone="LMK-Face_oval_chin", id_landmark=152, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.0, -0.056, 0.206), motion_mode=MotionMode.LANDMARK),
    
    "LMK-Face_oval1.R":         LandmarkBoneMap(bone="LMK-Face_oval1.R", id_landmark=109, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.038, -0.063, 0.472),     motion_mode=MotionMode.LANDMARK),
    "LMK-Face_oval2.R":         LandmarkBoneMap(bone="LMK-Face_oval2.R", id_landmark=103, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.082, -0.035, 0.461),     motion_mode=MotionMode.LANDMARK),
    "LMK-Face_oval3.R":         LandmarkBoneMap(bone="LMK-Face_oval3.R", id_landmark=234, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.11, 0.054, 0.36),        motion_mode=MotionMode.LANDMARK),
    "LMK-Face_oval4.R":         LandmarkBoneMap(bone="LMK-Face_oval4.R", id_landmark=132, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.106, 0.061, 0.316),      motion_mode=MotionMode.LANDMARK),
    "LMK-Face_oval5.R":         LandmarkBoneMap(bone="LMK-Face_oval5.R", id_landmark=150, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.057, -0.016, 0.233),     motion_mode=MotionMode.LANDMARK),
    ##################################################################
    #                            NOSE                                #
    ##################################################################
    "LMK-Nose_tip":          LandmarkBoneMap(bone="LMK-Nose_tip",    id_landmark=4,    parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.0, -0.112, 0.314),      motion_mode=MotionMode.LANDMARK),
    "LMK-Nose_base":         LandmarkBoneMap(bone="LMK-Nose_base",   id_landmark=168,  parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.0, -0.083, 0.381),      motion_mode=MotionMode.LANDMARK),
    "LMK-Nostril.L":         LandmarkBoneMap(bone="LMK-Nostril.L",   id_landmark=358,  parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.031, -0.069, 0.311),    motion_mode=MotionMode.LANDMARK),
    "LMK-Nostril.R":         LandmarkBoneMap(bone="LMK-Nostril.R",   id_landmark=129,  parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.031, -0.069, 0.311),   motion_mode=MotionMode.LANDMARK),

    ##################################################################
    #                            CHEEK                               #
    ##################################################################
    "LMK-Cheek_upp.L":          LandmarkBoneMap(bone="LMK-Cheek_upp.L", id_landmark=280, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.078, -0.043, 0.339),   motion_mode=MotionMode.LANDMARK),
    "LMK-Cheek_low.L":          LandmarkBoneMap(bone="LMK-Cheek_low.L", id_landmark=426, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.054, -0.056, 0.290),   motion_mode=MotionMode.LANDMARK),
    "LMK-Cheek_in.L":           LandmarkBoneMap(bone="LMK-Cheek_in.L",  id_landmark=266, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.044, -0.062, 0.329),   motion_mode=MotionMode.LANDMARK),
    "LMK-Cheek_out.L":          LandmarkBoneMap(bone="LMK-Cheek_out.L", id_landmark=416, parent_landmark=None,    parent_bone="LMK-Root", rest_position=(0.079, -0.021, 0.284),   motion_mode=MotionMode.LANDMARK),

    "LMK-Cheek_upp.R":          LandmarkBoneMap(bone="LMK-Cheek_upp.R", id_landmark=50,    parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.078, -0.043, 0.339), motion_mode=MotionMode.LANDMARK),
    "LMK-Cheek_low.R":          LandmarkBoneMap(bone="LMK-Cheek_low.R", id_landmark=206,   parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.054, -0.056, 0.290), motion_mode=MotionMode.LANDMARK),
    "LMK-Cheek_in.R":           LandmarkBoneMap(bone="LMK-Cheek_in.R",  id_landmark=36,    parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.044, -0.062, 0.329), motion_mode=MotionMode.LANDMARK),
    "LMK-Cheek_out.R":          LandmarkBoneMap(bone="LMK-Cheek_out.R", id_landmark=192,   parent_landmark=None,    parent_bone="LMK-Root", rest_position=(-0.079, -0.021, 0.284), motion_mode=MotionMode.LANDMARK),

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

FACE_MAPPING = {nome: BoneMap(*riga) for nome, riga in _TABELLA.items()}
LANDMARKERS_FACE_MAPPING = {nome: BoneMap(*riga) for nome, riga in _LANDMARKS_BONES_LUT.items()}
#ossa per la rotazione della mandibola con centro di rotazione all'altezza delle orecchie
ROTATION_BONES = {
    "Jaw": BONE_SHAPES["Jaw"],
}

LM_SIDE_R   = 234   # bordo guancia destra del soggetto
LM_SIDE_L   = 454   # bordo guancia sinistra del soggetto
LM_FOREHEAD = 10    # centro fronte
LM_NASION   = 168   # radice del naso, tra gli occhi

MIN_PAIR_DIST = 0.01

# Ampiezze tarate a mano su modello e webcam di riferimento.
# Con 1.0 lo spostamento dei landmark e' riportato 1:1 sulle proporzioni del rig.
AMPLITUDE   = 1.00   # moltiplicatore globale delle espressioni facciali (non la testa)
MOUTH_GAIN  = 0.5    # Lip_Upper*, Lip_Lower*, Mouth_Corner_*: scala le labbra insieme
# Apertura della mandibola, separata dalle labbra: con MOUTH_GAIN a 0.5 la
# bocca spalancata ruotava Jaw di soli 6-7 gradi. 1.5 porta a ~20 gradi;
# il tetto resta MAX_JAW_ANGLE.
JAW_GAIN    = 1.25   # 1.5 apriva leggermente troppo
# Angoli della bocca, separati dalle labbra: con MOUTH_GAIN a 0.5 il bacio
# stringeva la bocca di Steve del 10% contro il 20% misurato. 1.0 = movimento
# reale. Vale anche per il sorriso, che si allarga di piu'.
MOUTH_CORNER_GAIN = 1.0
EYE_GAIN    = 1.00   # Eye_L/R, Eyelid_Up/Low_L/R
BROW_GAIN   = 0.375  # Brow_L/R (stessa ampiezza di prima, quando AMPLITUDE era 0.5)
HEAD_GAIN   = 0.50   # traslazione di Head
HEAD_ROT_GAIN = 1.00 # rotazione di Head: la matrice di posa di MediaPipe e' gia' in scala reale

# Larghezza del viso (landmark 234-454) del modello canonico MediaPipe, in cm:
# converte la traslazione della matrice di posa in larghezze di viso.
FACE_WIDTH_CM = 15.0

# Blendshape MediaPipe (punteggi 0..1). Valore del punteggio che vale "movimento
# completo"; lo zero e' il valore misurato in calibrazione a viso rilassato.
BLENDSHAPE_FULL = {
    "eyeBlinkLeft":   0.60,   # misurato: a occhio chiuso il punteggio arriva a ~0.6-0.67
    "eyeBlinkRight":  0.60,
    "eyeWideLeft":    0.60,
    "eyeWideRight":   0.60,
    "eyeSquintLeft":  0.60,
    "eyeSquintRight": 0.60,
    "jawOpen":        0.70,   # solo per il log: la mandibola segue i landmark del mento
}
# True se occhiolino sinistro chiude l'occhio destro del modello (Mirror X spento).
BLENDSHAPE_SWAP_LR = False

# Corsa delle palpebre, in frazione dell'apertura dell'occhio del rig
# (distanza Eyelid_Up - Eyelid_Low a riposo).
EYELID_UPPER_CLOSE  = 0.70   # palpebra superiore a occhio chiuso (0.55 lasciava l'occhio socchiuso)
EYELID_LOWER_CLOSE  = 0.15   # palpebra inferiore a occhio chiuso
EYELID_UPPER_WIDE   = 0.25   # sollevamento a occhi sgranati
EYELID_LOWER_SQUINT = 0.15   # sollevamento della palpebra inferiore strizzando

# Pesi delle palpebre, disegnati sulla geometria al click di Collega Manualmente
# (il bone heat non e' affidabile sulle palpebre): una fascia lungo la
# palpebra, piena al centro e a zero fuori, con le altre ossa ridotte di
# conseguenza.
EYELID_SPREAD_RADIUS  = 0.28   # semi-larghezza della palpebra, in frazione della distanza fra gli occhi
EYELID_CORNER_DROP    = 0.35   # quanto si muovono meno gli angoli: 0 = come il centro, 1 = fermi
EYELID_SPREAD_HEIGHT  = 0.12   # meta' altezza della fascia pesata attorno all'osso, stessa unita' di RADIUS

# Stampa in console, una volta al secondo, angoli della testa e blendshape.
DEBUG_MOCAP_LOG = True


# parametri per filtro 1Euro
ONE_EURO_MIN_CUTOFF = 1.0  # in Hz. Più basso = più smoothing da fermo, più lag sui movimenti
# Più alto = meno lag sui movimenti rapidi, più rumore residuo.
# La velocità è misurata in larghezze-viso/s (traslazioni) e rad/s (rotazioni).
ONE_EURO_BETA = 3.0

CALIBRATION_FRAMES = 30
HEAD_DEPTH_GAIN = 1.0
MIN_FEATURE_SCALE = 0.35
MAX_FEATURE_SCALE = 4.0
MIN_LEVER_DOWN = 0.3

#apertura massima della mandibola in gradi
MAX_JAW_ANGLE = 30.0
