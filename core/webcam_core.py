import cv2
import mediapipe as mp


class FaceTracker:
    def __init__(self):
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,            # da impostare il numero di facce da elaborare(possiamo lasciare a 1)
            refine_landmarks=True,      # punti più dettagliati per occhi e bocca
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.cap = None

    def start(self):
        """Apre la connessione con la webcam."""
        self.cap = cv2.VideoCapture(0) # 0 è la webcam di default
        if not self.cap.isOpened():
            print("Errore: impossibile aprire la webcam")
            return False
        return True

    def read_landmarks(self):
        """(landmark del primo viso, aspect ratio del frame), o None.

        None copre tutti i casi in cui non c'e' niente da applicare: frame non
        letto, nessun viso riconosciuto. Chi chiama fa un solo controllo.
        """
        success, image = self.cap.read()
        if not success:
            return None

        # MediaPipe vuole immagini in RGB
        results = self.face_mesh.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        if not results.multi_face_landmarks:
            return None

        height, width = image.shape[:2]
        aspect = width / height if height else 1.0
        return results.multi_face_landmarks[0].landmark, aspect

    def stop(self):
        """Rilascia la webcam."""
        # Niente cv2.destroyAllWindows(): finestre non se ne aprono piu'.
        if self.cap:
            self.cap.release()
            self.cap = None
