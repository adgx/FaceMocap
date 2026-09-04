import time
import numpy as np
import cv2
from cv2 import UMat
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision.face_landmarker import FaceLandmarkerResult
from typing import NamedTuple
from mediapipe.tasks.python.vision import drawing_utils
from mediapipe.tasks.python.vision import drawing_styles

#utils stuff
def curr_ms_time() -> int:
    return round(time.time() * 1000)

def draw_landmarks_on_image(rgb_image, detection_result):
    if detection_result is None:
        return rgb_image
    face_landmarks_list = detection_result.face_landmarks
    annotated_image = np.copy(rgb_image)

    #loop over detected faces
    for idx in range(len(face_landmarks_list)):
        face_landmarks = face_landmarks_list[idx]

        #draw face landmarks
        drawing_utils.draw_landmarks(
            image=annotated_image,
            landmark_list=face_landmarks,
            connections=vision.FaceLandmarksConnections.FACE_LANDMARKS_TESSELATION,
            landmark_drawing_spec=None,
            connection_drawing_spec=drawing_styles.get_default_face_mesh_tesselation_style())
        
        drawing_utils.draw_landmarks(
            image=annotated_image,
            landmark_list=face_landmarks,
            connections=vision.FaceLandmarksConnections.FACE_LANDMARKS_CONTOURS,
            landmark_drawing_spec=None,
            connection_drawing_spec=drawing_styles.get_default_face_mesh_contours_style())

        drawing_utils.draw_landmarks(
            image=annotated_image,
            landmark_list=face_landmarks,
            connections=vision.FaceLandmarksConnections.FACE_LANDMARKS_LEFT_IRIS,
            landmark_drawing_spec=None,
            connection_drawing_spec=drawing_styles.get_default_face_mesh_iris_connections_style())

        drawing_utils.draw_landmarks(
            image=annotated_image,
            landmark_list=face_landmarks,
            connections=vision.FaceLandmarksConnections.FACE_LANDMARKS_RIGHT_IRIS,
            landmark_drawing_spec=None,
            connection_drawing_spec=drawing_styles.get_default_face_mesh_iris_connections_style())
    
    return annotated_image


def result_cb(result: FaceLandmarkerResult, output_image: mp.Image, timestamp_ms: int):
    print('face landmarker result: {}'.format(result))
    FaceTracker.result = result


class FaceTracker:
    
    result: FaceLandmarkerResult = None
    def __init__(self):
        #set the model's path
        self.model_path = "./face_landmarker_v2.task"
        
        #alias time
        BaseOptions = mp.tasks.BaseOptions
        FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
        FaceLandmarkerResult = mp.tasks.vision.FaceLandmarkerResult
        VisionRunningMode = mp.tasks.vision.RunningMode
        FaceLandmarker = mp.tasks.vision.FaceLandmarker

        self.options = FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=self.model_path),
                                                running_mode=VisionRunningMode.LIVE_STREAM,
                                                num_faces=1,
                                                result_callback=result_cb)
        self.detector = vision.FaceLandmarker.create_from_options(self.options)
        #self.mp_face_mesh = mp.solutions.face_mesh
        #self.face_mesh = self.mp_face_mesh.FaceMesh(
        #    max_num_faces=1,            # da impostare il numero di facce da elaborare(possiamo lasciare a 1)
        #    refine_landmarks=True,      # punti più dettagliati per occhi e bocca
        #    min_detection_confidence=0.5,
        #    min_tracking_confidence=0.5
        #)
        #self.mp_drawing = mp.solutions.drawing_utils
        #self.mp_drawing_styles = mp.solutions.drawing_styles
        #capture data
        self.cap = None
    

    def start(self) -> bool:
        """Apre la connessione con la webcam.
           Open a connection with the default web cam
        """
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
        #image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        #results = self.face_mesh.process(image_rgb)
        #If we want to use directly the facke landmark model
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
        self.detector.detect_async(image=mp_image, timestamp_ms=curr_ms_time())
        #if results.multi_face_landmarks:
        #    for face_landmarks in results.multi_face_landmarks:
        #        self.mp_drawing.draw_landmarks(
        #            image=image,
        #            landmark_list=face_landmarks,
        #            connections=self.mp_face_mesh.FACEMESH_TESSELATION,
        #            landmark_drawing_spec=None,
        #            connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_tesselation_style()
        #        )
        #new on main
        #if not results.multi_face_landmarks:
        #    return None
#
        #height, width = image.shape[:2]
        #aspect = width / height if height else 1.0
        #return results.multi_face_landmarks[0].landmark, aspect
        #results = None
        return image, results

    def stop(self) -> None:
        """Rilascia la webcam e chiude le finestre."""
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
    
    def __setattr__(self, name, value):
        if name == "result":
            raise AttributeError("result is a class attribute")
        
        super().__setattr__(name, value)


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
            
            annoted_frame = draw_landmarks_on_image(frame, FaceTracker.result)
            cv2.imshow("FaceMocap - Debug Webcam", annoted_frame)
            
            if cv2.waitKey(5) & 0xFF == ord('q'):
                break
                
        tracker.stop()