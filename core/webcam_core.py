import sys
from pathlib import Path
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
from . import config
from .. import MODEL_DIR, MODEL_NAME

#utils stuff

class Debug:
    SHOW_ALL: bool = False 
    SHOW_LANDMARK_LIPS: bool = False
    SHOW_LANDMARK_LEFT_EYE: bool = False
    SHOW_LANDMARK_LEFT_EYEBROW: bool = False
    SHOW_LANDMARK_LEFT_IRIS: bool = False
    SHOW_LANDMARK_RIGHT_EYE: bool = False
    SHOW_LANDMARK_RIGHT_EYEBROW: bool = False
    SHOW_LANDMARK_RIGHT_IRIS: bool = False
    SHOW_LANDMARK_FACE_OVAL: bool = False
    SHOW_LANDMARK_TASSELATION: bool = False
    SHOW_LANDMARK_FACEMOCAP: bool = True

LANDMARKERS_INDEX_LIPS: list[int] = list(dict.fromkeys( idx 
                                                        for connession in vision.FaceLandmarksConnections.FACE_LANDMARKS_LIPS
                                                        for idx in (connession.start, connession.end)))

LANDMARKERS_INDEX_LEFT_EYE: list[int] = list(dict.fromkeys( idx 
                                                        for connession in vision.FaceLandmarksConnections.FACE_LANDMARKS_LEFT_EYE
                                                        for idx in (connession.start, connession.end)))

LANDMARKERS_INDEX_LEFT_EYEBROW: list[int] = list(dict.fromkeys( idx 
                                                        for connession in vision.FaceLandmarksConnections.FACE_LANDMARKS_LEFT_EYEBROW
                                                        for idx in (connession.start, connession.end)))

LANDMARKERS_INDEX_LEFT_IRIS: list[int] = list(dict.fromkeys( idx 
                                                        for connession in vision.FaceLandmarksConnections.FACE_LANDMARKS_LEFT_IRIS
                                                        for idx in (connession.start, connession.end)))

LANDMARKERS_INDEX_RIGHT_EYE: list[int] = list(dict.fromkeys( idx 
                                                        for connession in vision.FaceLandmarksConnections.FACE_LANDMARKS_RIGHT_EYE
                                                        for idx in (connession.start, connession.end)))

LANDMARKERS_INDEX_RIGHT_EYEBROW: list[int] = list(dict.fromkeys( idx 
                                                        for connession in vision.FaceLandmarksConnections.FACE_LANDMARKS_RIGHT_EYEBROW
                                                        for idx in (connession.start, connession.end)))

LANDMARKERS_INDEX_RIGHT_IRIS: list[int] = list(dict.fromkeys( idx 
                                                        for connession in vision.FaceLandmarksConnections.FACE_LANDMARKS_RIGHT_IRIS
                                                        for idx in (connession.start, connession.end)))

LANDMARKERS_INDEX_FACE_OVAL: list[int] = list(dict.fromkeys( idx 
                                                        for connession in vision.FaceLandmarksConnections.FACE_LANDMARKS_FACE_OVAL
                                                        for idx in (connession.start, connession.end)))

LANDMARKERS_INDEX_TASSELATION: list[int] = list(dict.fromkeys( idx 
                                                        for connession in vision.FaceLandmarksConnections.FACE_LANDMARKS_TESSELATION
                                                        for idx in (connession.start, connession.end)))
LANDMARKERS_INDEX_ADVANCE_FACEMOCAP: list[int] = list(landmark[0] for landmark in config.LANDMARKERS_FACE_MAPPING.values())
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

        if Debug.SHOW_ALL:
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
        
        if Debug.SHOW_LANDMARK_LIPS:
            drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=[face_landmarks[idx] for idx in LANDMARKERS_INDEX_LIPS],
                connection_drawing_spec=None)
        
        if Debug.SHOW_LANDMARK_LEFT_EYE:
            drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=[face_landmarks[idx] for idx in LANDMARKERS_INDEX_LEFT_EYE],
                connection_drawing_spec=None)
        
        if Debug.SHOW_LANDMARK_LEFT_EYEBROW:
            drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=[face_landmarks[idx] for idx in LANDMARKERS_INDEX_LEFT_EYEBROW],
                connection_drawing_spec=None)
        
        if Debug.SHOW_LANDMARK_LEFT_IRIS:
            drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=[face_landmarks[idx] for idx in LANDMARKERS_INDEX_LEFT_IRIS],
                connection_drawing_spec=None)
                
        if Debug.SHOW_LANDMARK_RIGHT_EYE:
            drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=[face_landmarks[idx] for idx in LANDMARKERS_INDEX_RIGHT_EYE],
                connection_drawing_spec=None)
        
        if Debug.SHOW_LANDMARK_RIGHT_EYEBROW:
            drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=[face_landmarks[idx] for idx in LANDMARKERS_INDEX_RIGHT_EYEBROW],
                connection_drawing_spec=None)
        
        if Debug.SHOW_LANDMARK_RIGHT_IRIS:
            drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=[face_landmarks[idx] for idx in LANDMARKERS_INDEX_RIGHT_IRIS],
                connection_drawing_spec=None)
        if Debug.SHOW_LANDMARK_FACE_OVAL:
            drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=[face_landmarks[idx] for idx in LANDMARKERS_INDEX_FACE_OVAL],
                connection_drawing_spec=None)
        if Debug.SHOW_LANDMARK_TASSELATION:
            drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=[face_landmarks[idx] for idx in LANDMARKERS_INDEX_TASSELATION],
                connection_drawing_spec=None)
        if Debug.SHOW_LANDMARK_FACEMOCAP:
            drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=[face_landmarks[idx] for idx in LANDMARKERS_INDEX_ADVANCE_FACEMOCAP],
                connection_drawing_spec=None)
    return annotated_image


def result_cb(result: FaceLandmarkerResult, output_image: mp.Image, timestamp_ms: int):
    print('face landmarker result: {}'.format(result))
    FaceTracker.result = result


class FaceTracker:
    
    result: FaceLandmarkerResult = None

    def __init__(self):
        #set the model's path
        self.model_path = str(MODEL_DIR / MODEL_NAME)
        
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
    
    def read_frame(self) -> cv2.typing.MatLike | None:
        """Legge un singolo frame, lo processa e restituisce i dati.
           Read and process a single frame 
        """
        success, image = self.cap.read()
        if not success:
            return None, None

        #Directly use of the facke landmark model
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
        self.detector.detect_async(image=mp_image, timestamp_ms=curr_ms_time())
        return image

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
            frame= tracker.read_frame()
            if frame is None:
                break
            
            annoted_frame = draw_landmarks_on_image(frame, FaceTracker.result)
            cv2.imshow("FaceMocap - Debug Webcam", annoted_frame)
            
            if cv2.waitKey(5) & 0xFF == ord('q'):
                break
                
        tracker.stop()