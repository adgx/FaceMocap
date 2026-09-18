import cv2
import mediapipe as mp

mp_drawing = mp.solutions.drawing_utils
mp_face_mesh = mp.solutions.face_mesh
WINDOW_NAME = 'FaceMocap - Webcam Preview (Premi ESC su Blender)'

class FaceTracker:
    def __init__(self, show_preview=True):
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,            # da impostare il numero di facce da elaborare(possiamo lasciare a 1)
            refine_landmarks=True,      # punti più dettagliati per occhi e bocca
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.cap = None
        self.show_preview = show_preview
        self._window_open = False

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

        # MediaPipe vuole immagini in RGB per il calcolo
        results = self.face_mesh.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        
        if self.show_preview:
            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    # Disegna la maschera verde sull'immagine originale
                    mp_drawing.draw_landmarks(
                        image=image,
                        landmark_list=face_landmarks,
                        connections=mp_face_mesh.FACEMESH_TESSELATION,
                        landmark_drawing_spec=None,
                        connection_drawing_spec=mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=1, circle_radius=1)
                    )
            
            preview_image = cv2.flip(image, 1)
            cv2.imshow(WINDOW_NAME, preview_image)
            self._window_open = True
            cv2.waitKey(1)

            try:
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    self.show_preview = False
                    self._window_open = False
            except cv2.error:
                self.show_preview = False
                self._window_open = False
                
        elif self._window_open:
            cv2.destroyAllWindows()
            for _ in range(5):
                cv2.waitKey(1)
            self._window_open = False


        if not results.multi_face_landmarks:
            return None

        height, width = image.shape[:2]
        aspect = width / height if height else 1.0
        return results.multi_face_landmarks[0].landmark, aspect

    def stop(self):
        """Rilascia la webcam e chiude eventuali finestre."""
        if self.cap:
            self.cap.release()
            self.cap = None
            
        if getattr(self, '_window_open', False):
            cv2.destroyAllWindows()
            cv2.waitKey(1)
            self._window_open = False