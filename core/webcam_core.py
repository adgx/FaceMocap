import sys
from pathlib import Path
import threading
import time
import numpy as np
import cv2
import os
from cv2 import UMat
import mediapipe as mp
import urllib.request
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision.face_landmarker import FaceLandmarkerResult
from mediapipe.tasks.python.components.containers import NormalizedLandmark
from typing import NamedTuple

from . import config
from .. import MODEL_DIR, MODEL_NAME

# mediapipe >= 1.0: le utility di disegno stanno nelle Tasks API e accettano
# direttamente le liste di NormalizedLandmark (niente piu' protobuf)
from mediapipe.tasks.python.vision import drawing_utils
from mediapipe.tasks.python.vision import drawing_styles

WINDOW_NAME = 'FaceMocap - Webcam Preview (Press ESC in Blender)'
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

def ensure_model_exists(model_path):
    """Verifica se il file del modello esiste; in caso contrario, lo scarica automaticamente."""
    if os.path.exists(model_path):
        return True
    
    # Crea la cartella di destinazione se non esiste
    model_dir = os.path.dirname(model_path)
    os.makedirs(model_dir, exist_ok=True)
    
    print(f"FaceMocap: Modello di MediaPipe non trovato. Download in corso da {MODEL_URL}...")
    try:
        urllib.request.urlretrieve(MODEL_URL, model_path)
        print("FaceMocap: Download completato con successo!")
        return True
    except Exception as e:
        print(f"FaceMocap Errore: Impossibile scaricare il modello automaticamente: {e}")
        return False

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
    SHOW_LANDMARK_FACEMOCAP: bool = False
    SHOW_LANDMARK_BOUNDS_FACEMOCAP: bool = True


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
LANDMARKERS_INDEX_BOUNDS_FACEMOCAP: list[int] = [config.LM_SIDE_R, config.LM_SIDE_L, config.LM_FOREHEAD, config.LM_NASION] 

def curr_ms_time() -> int:
    """Tempo monotono in ms: detect_async richiede timestamp crescenti."""
    return round(time.monotonic() * 1000)

def draw_landmarks_on_image(bgr_image, detection_result):
    if detection_result is None or not getattr(detection_result, 'face_landmarks', None):
        return bgr_image

    annotated_image = np.copy(bgr_image)

    for face_landmarks in detection_result.face_landmarks:
        
        if Debug.SHOW_ALL:
            proto_all = face_landmarks
            
            drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=proto_all,
                connections=vision.FaceLandmarksConnections.FACE_LANDMARKS_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=drawing_styles.get_default_face_mesh_tesselation_style())

            drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=proto_all,
                connections=vision.FaceLandmarksConnections.FACE_LANDMARKS_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=drawing_styles.get_default_face_mesh_contours_style())

            drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=proto_all,
                connections=vision.FaceLandmarksConnections.FACE_LANDMARKS_LEFT_IRIS,
                landmark_drawing_spec=None,
                connection_drawing_spec=drawing_styles.get_default_face_mesh_iris_connections_style())

            drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=proto_all,
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
                
        if Debug.SHOW_LANDMARK_BOUNDS_FACEMOCAP:
            drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=[face_landmarks[idx] for idx in LANDMARKERS_INDEX_BOUNDS_FACEMOCAP],
                connection_drawing_spec=None)
    return annotated_image

class TrackingFrame(NamedTuple):
    landmarks: list[NormalizedLandmark]
    aspect: float                 # aspect ratio del frame
    time: float                   # istante del frame analizzato, in secondi
    blendshapes: dict | None      # nome blendshape -> punteggio 0..1
    pose: np.ndarray | None       # 4x4, modello canonico -> camera (cm, assi OpenGL)


def result_cb(result: FaceLandmarkerResult, output_image: mp.Image, timestamp_ms: int):
    FaceTracker.result = result
    FaceTracker.result_timestamp_ms = timestamp_ms


class FaceTracker:

    result: FaceLandmarkerResult = None
    result_timestamp_ms: int = -1

    def __init__(self, show_preview=True):
        #set the model's path
        self.model_path = str(MODEL_DIR / MODEL_NAME)

        if not ensure_model_exists(self.model_path):
            raise RuntimeError("MediaPipe model not found and download failed: " + self.model_path)

        # niente risultati rimasti da una sessione precedente
        FaceTracker.result = None
        FaceTracker.result_timestamp_ms = -1

        #alias time
        BaseOptions = mp.tasks.BaseOptions
        FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
        VisionRunningMode = mp.tasks.vision.RunningMode

        self.options = FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=self.model_path),
                                                running_mode=VisionRunningMode.LIVE_STREAM,
                                                num_faces=1,
                                                output_face_blendshapes=True,
                                                output_facial_transformation_matrixes=True,
                                                result_callback=result_cb)
        self.detector = vision.FaceLandmarker.create_from_options(self.options)

        #capture data
        self.cap = None
        self.show_preview = show_preview
        self._window_open = False
        self._last_sent_ms = -1
        self._last_read_ms = -1
        self.stats = self._stats_vuote()

        # Cattura in un thread: tiene SOLO l'ultimo frame. Se la leggesse il
        # timer di Blender, a meno tick/s dei frame/s della webcam i frame si
        # accumulerebbero nel buffer di OpenCV e il rig mostrerebbe sempre il
        # passato (effetto rallentatore). Il thread invia anche i frame a
        # MediaPipe, che cosi' lavora al ritmo della webcam.
        self._thread = None
        self._running = False
        self._lock = threading.Lock()
        self._frame = None
        self._frame_id = 0
        self._used_id = 0

    @staticmethod
    def _stats_vuote():
        return {"catturati": 0, "letture": 0, "nuovi": 0, "risultati": 0, "eta_ms": 0.0}

    def pop_stats(self):
        """Contatori di prestazione dall'ultima chiamata, poi azzerati."""
        stats, self.stats = self.stats, self._stats_vuote()
        return stats

    def start(self, camera_id: int = 0) -> bool:
        """Apre la connessione con la webcam e avvia il thread di cattura.
           Open a connection with the selected web cam (0 = default)
        """
        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            print("Errore: impossibile aprire la webcam %d" % camera_id)
            return False
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop,
                                        name="FaceMocap-capture", daemon=True)
        self._thread.start()
        return True

    def _capture_loop(self) -> None:
        """Legge la webcam al suo ritmo e conserva solo l'ultimo frame."""
        while self._running:
            try:
                success, image = self.cap.read()
                if not success:
                    time.sleep(0.005)
                    continue
                self._send(image)
            except Exception as e:
                print("FaceMocap - errore nel thread di cattura: %s" % e)
                time.sleep(0.05)
                continue
            with self._lock:
                self._frame = image
                self._frame_id += 1
            self.stats["catturati"] += 1

    def _send(self, image) -> None:
        """Invia il frame (BGR da OpenCV) a MediaPipe, che lo vuole in RGB."""
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp = max(curr_ms_time(), self._last_sent_ms + 1)
        self._last_sent_ms = timestamp
        self.detector.detect_async(image=mp_image, timestamp_ms=timestamp)

    def _latest_frame(self):
        """(frame, e' nuovo dall'ultima lettura) dell'ultimo frame catturato."""
        with self._lock:
            image, frame_id = self._frame, self._frame_id
        nuovo = frame_id != self._used_id
        self._used_id = frame_id
        return image, nuovo

    def read_frame(self):
        """Attende un frame nuovo e lo restituisce (usata dal test qui sotto).
           Wait for a new frame
        """
        while self._running:
            image, nuovo = self._latest_frame()
            if nuovo:
                return image
            time.sleep(0.002)
        return None

    def read_landmarks(self) -> TrackingFrame | None:
        """Landmark, blendshape e matrice di posa del primo viso, o None.

        None copre tutti i casi in cui non c'e' niente da applicare: nessun
        frame ancora, nessun viso riconosciuto, nessun risultato NUOVO
        dall'ultima chiamata (in LIVE_STREAM il risultato arriva in modo
        asincrono). L'istante e' il timestamp del frame analizzato, da usare
        nei filtri. Non blocca: il frame lo legge il thread di cattura.
        """
        image, nuovo = self._latest_frame()
        self.stats["letture"] += 1
        if image is None:
            return None
        if nuovo:
            self.stats["nuovi"] += 1

        result = FaceTracker.result
        result_ms = FaceTracker.result_timestamp_ms

        # la preview si aggiorna anche quando il viso non e' riconosciuto
        if self.show_preview and nuovo:
            annotated_image = draw_landmarks_on_image(image, result)
            cv2.imshow(WINDOW_NAME, annotated_image)
            self._window_open = True
            cv2.waitKey(1)

            try:
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    self.show_preview = False
                    self._window_open = False
            except cv2.error:
                self.show_preview = False
                self._window_open = False

        elif not self.show_preview and self._window_open:
            cv2.destroyAllWindows()
            for _ in range(5):
                cv2.waitKey(1)
            self._window_open = False

        if result is None or not result.face_landmarks:
            return None
        if result_ms == self._last_read_ms:
            return None
        self._last_read_ms = result_ms
        self.stats["risultati"] += 1
        # da quando il frame e' stato spedito a MediaPipe a quando lo usiamo
        self.stats["eta_ms"] += curr_ms_time() - result_ms

        height, width = image.shape[:2]
        aspect = width / height if height else 1.0

        blendshapes = None
        if result.face_blendshapes:
            blendshapes = {c.category_name: c.score for c in result.face_blendshapes[0]}
        pose = None
        if result.facial_transformation_matrixes:
            pose = np.asarray(result.facial_transformation_matrixes[0], dtype=float)

        return TrackingFrame(result.face_landmarks[0], aspect, result_ms / 1000.0,
                             blendshapes, pose)

    def stop(self) -> None:
        """Ferma la cattura, rilascia la webcam, chiude il detector e le finestre."""
        # il thread usa cap e detector: va fermato prima di rilasciarli
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.detector:
            self.detector.close()
            self.detector = None
        FaceTracker.result = None
        FaceTracker.result_timestamp_ms = -1
        cv2.destroyAllWindows()

    def __setattr__(self, name, value):
        if name in ("result", "result_timestamp_ms"):
            raise AttributeError(name + " is a class attribute")

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
