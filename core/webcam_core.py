import sys
from pathlib import Path

import cv2
import mediapipe as mp

class FaceTracker:
    def __init__(self):

        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,            # da impostare il numero di facce da elaborare(possiamo lasciare a 1)
            refine_landmarks=True,      # punti più dettagliati per occhi e bocca
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        self.cap = None

    def start(self):
        """Apre la connessione con la webcam."""
        self.cap = cv2.VideoCapture(0) # 0 è la webcam di default
        if not self.cap.isOpened():
            print("Errore: impossibile aprire la webcam")
            return False
        return True

    def read_frame(self):
        """Legge un singolo frame, lo processa e restituisce i dati."""
        success, image = self.cap.read()
        if not success:
            return None, None

        # MediaPipe vuole immagini in RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        results = self.face_mesh.process(image_rgb)

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                self.mp_drawing.draw_landmarks(
                    image=image,
                    landmark_list=face_landmarks,
                    connections=self.mp_face_mesh.FACEMESH_TESSELATION,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_tesselation_style()
                )

        return image, results

    def stop(self):
        """Rilascia la webcam e chiude le finestre."""
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()


#per test
if __name__ == "__main__":
    ADDON_DIR = Path(__file__).parent.parent 
    LIB_DIR = ADDON_DIR / "site-packages"
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))

    tracker = FaceTracker()
    if tracker.start():
        print("Premi 'q' sulla finestra del video per uscire.")
        while True:
            frame, results = tracker.read_frame()
            if frame is None:
                break
            
            cv2.imshow("FaceMocap - Debug Webcam", frame)
            
            if cv2.waitKey(5) & 0xFF == ord('q'):
                break
                
        tracker.stop()