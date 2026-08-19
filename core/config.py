# Mappa di base della faccia. 
# Struttura: "Nome_Osso": (Index_MediaPipe, Index_Genitore_MediaPipe, Nome_Osso_Genitore, (pos_x, pos_y, pos_z))

FACE_MAPPING = {
    "Head":           (1,   None, None,   (0.0,  0.0,  0.0)),
    "Jaw":            (152, 1,    "Head", (0.0, -0.1, -0.5)),
    "Eye_L":          (159, 1,    "Head", (0.2, -0.2,  0.2)),
    "Eye_R":          (386, 1,    "Head", (-0.2, -0.2,  0.2)),
    "Brow_L":         (105, 1,    "Head", (0.2, -0.25, 0.4)),
    "Brow_R":         (334, 1,    "Head", (-0.2, -0.25, 0.4)),
    "Mouth_Corner_L": (61,  152,  "Jaw",  (0.15, -0.15, -0.3)),
    "Mouth_Corner_R": (291, 152,  "Jaw",  (-0.15, -0.15, -0.3))
}