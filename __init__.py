bl_info = {
    "name": "FaceMocap",
    "author": "adgx and F3de22",
    "blender": (4, 2, 0),
    "category": "Animation",
}

import bpy
import subprocess
import importlib
import importlib.metadata
import sys
from . import auto_load
from pathlib import Path

ADDON_DIR = Path(__file__).parent
LIB_DIR = ADDON_DIR / "site-packages"
LIB_DIR.mkdir(exist_ok=True)
MODEL_DIR = LIB_DIR / "model"
MODEL_NAME = "face_landmarker_v2.task"
MODEL_DIR.mkdir(exist_ok=True)

if str(LIB_DIR) not in sys.path:
    sys.path.append(str(LIB_DIR))
 
 
def _run(cmd):
    print(f"\033[34mFaceMocap: runs -> {' '.join(cmd)}\033[0m")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode != 0:
        print(f"\033[31mFaceMocap: Warning, command failed with exit code {result.returncode}: {' '.join(cmd)}\033[0m")
    return result.returncode == 0

MEDIAPIPE_VERSION = "1.1.0"
OPENCV_VERSION = "4.11.0.86"


def _installed_version(dist_name):
    """Versione installata di un pacchetto, senza importarlo (None se assente)."""
    try:
        return importlib.metadata.version(dist_name)
    except importlib.metadata.PackageNotFoundError:
        return None


#installa le dipendenze se non sono già installate (o se la versione è diversa)
def install_dependencies():
    python_exe = sys.executable
    print(f"\033[34mFaceMocap: using Python interpreter -> {python_exe}\033[0m")
    print(f"\033[34mFaceMocap: local dependencies folder -> {LIB_DIR}\033[0m")
    missing_packages = []
    importlib.invalidate_caches()

    # mediapipe dipende da opencv-contrib-python, che fornisce anche cv2
    cv2_version = _installed_version("opencv-contrib-python")
    if cv2_version != OPENCV_VERSION:
        print(f"\033[31mFaceMocap: opencv-contrib-python {cv2_version} found, {OPENCV_VERSION} required\033[0m")
        missing_packages.append(f"opencv-contrib-python=={OPENCV_VERSION}")
    else:
        print(f"\033[32mFaceMocap: opencv-contrib-python version={cv2_version} detected\033[0m")

    mp_version = _installed_version("mediapipe")
    if mp_version != MEDIAPIPE_VERSION:
        print(f"\033[31mFaceMocap: mediapipe {mp_version} found, {MEDIAPIPE_VERSION} required\033[0m")
        missing_packages.append(f"mediapipe=={MEDIAPIPE_VERSION}")
    else:
        print(f"\033[32mFaceMocap: mediapipe version={mp_version} detected\033[0m")

    if missing_packages:
        print(f"\033[34mFaceMocap: Installing {missing_packages} in {LIB_DIR}. Wait...\033[0m")
        ok = _run([python_exe, "-m", "ensurepip"])
        ok = _run([python_exe, "-m", "pip", "install", "--upgrade", "pip"]) and ok
        ok = _run([
            python_exe, "-m", "pip", "install",
            "--upgrade",
            "--target", str(LIB_DIR),
            "numpy<2",
            f"opencv-contrib-python=={OPENCV_VERSION}",
            f"mediapipe=={MEDIAPIPE_VERSION}",
        ]) and ok
 
        if not ok:
            print("\033[31mFaceMocap: ERROR - one or more installation commands failed. See the output above.\033[0m")
        else:
            print("\033[32mFaceMocap: Dependencies installed successfully.\033[0m")
 
        importlib.invalidate_caches()
 
        for pkg_import, pkg_name in [("cv2", "opencv-contrib-python"), ("mediapipe", "mediapipe")]:
            try:
                importlib.import_module(pkg_import)
                print(f"\033[32mFaceMocap: Verification OK, '{pkg_import}' can be imported after installation.\033[0m")
            except ImportError as e:
                print(f"\033[31mFaceMocap: Verification FAILED for '{pkg_import}' ({pkg_name}): {e}\033[0m")

        if any(name in sys.modules for name in ("cv2", "mediapipe")):
            print("\033[33mFaceMocap: an older version was already loaded: restart Blender to use the new one.\033[0m")

    # Il modello face_landmarker.task viene scaricato (se manca) da
    # core/webcam_core.ensure_model_exists all'avvio del tracker.

def register():
    install_dependencies()
    auto_load.init()
    auto_load.register()

def unregister():
    from . import auto_load
    auto_load.unregister()