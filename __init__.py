bl_info = {
    "name": "FaceMocap",
    "author": "adgx and F3de22",
    "blender": (4, 2, 0),
    "category": "Animation",
}

import bpy
import subprocess
import importlib
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

#installa le dipendenze se non sono già installate
def install_dependencies():
    python_exe = sys.executable
    print(f"\033[34mFaceMocap: using Python interpreter -> {python_exe}\033[0m")
    print(f"\033[34mFaceMocap: local dependencies folder -> {LIB_DIR}\033[0m")
    missing_packages = []
 
    try:
        import cv2
        print(f"\033[32mFaceMocap: cv2 version={cv2.__version__} detected\033[0m")
    except ImportError as e:
        print(f"\033[31mFaceMocap: cv2 not found ({e})\033[0m")
        missing_packages.append("opencv-python==4.9.0.80")
 
    try:
        import mediapipe
        print(f"\033[32mFaceMocap: mediapipe version={mediapipe.__version__} detected\033[0m")
    except ImportError as e:
        print(f"\033[31mFaceMocap: mediapipe not found ({e})\033[0m")
        missing_packages.append("mediapipe==1.0.1")
 
    if missing_packages:
        print(f"\033[34mFaceMocap: Installing {missing_packages} in {LIB_DIR}. Wait...\033[0m")
        ok = _run([python_exe, "-m", "ensurepip"])
        ok = _run([python_exe, "-m", "pip", "install", "--upgrade", "pip"]) and ok
        ok = _run([
            python_exe, "-m", "pip", "install",
            "--target", str(LIB_DIR),
            "numpy<2", "protobuf<4", *missing_packages,
        ]) and ok 
 
        if not ok:
            print("\033[31mFaceMocap: ERROR - one or more installation commands failed. See the output above.\033[0m")
        else:
            print("\033[32mFaceMocap: Dependencies installed successfully.\033[0m")
 
        importlib.invalidate_caches()
 
        for pkg_import, pkg_name in [("cv2", "opencv-python"), ("mediapipe", "mediapipe")]:
            try:
                importlib.import_module(pkg_import)
                print(f"\033[32mFaceMocap: Verification OK, '{pkg_import}' can be imported after installation.\033[0m")
            except ImportError as e:
                print(f"\033[31mFaceMocap: Verification FAILED for '{pkg_import}' ({pkg_name}): {e}\033[0m")
        
    if not (MODEL_DIR / MODEL_NAME).exists:
        ok = _run([
            "wget",
            "-O", 
            str(MODEL_DIR / MODEL_NAME),
            "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
        ])
        print(f"\033[32mFacemocap: model: {str(MODEL_NAME)} downloaded in: {str(MODEL_DIR)}\033[0m")
    else: 
        print(f"\033[32mFacemocap: model: {str(MODEL_NAME)} detected at: {str(MODEL_DIR)}\033[0m")

def register():
    install_dependencies()
    auto_load.init()
    auto_load.register()

def unregister():
    from . import auto_load
    auto_load.unregister()