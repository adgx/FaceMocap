bl_info = {
    "name": "FaceMocap",
    "author": "adgx and F3de22",
    "blender": (4, 2, 0),
    "category": "Animation",
}


import bpy
import subprocess
import sys
from . import auto_load

auto_load.init()

#installa le dipendenze se non sono già installate
def install_dependencies():
    python_exe = sys.executable
    missing_packages = []

    try:
        import cv2
    except ImportError:
        missing_packages.append("opencv-python")
        
    try:
        import mediapipe
    except ImportError:
        missing_packages.append("mediapipe")
        
    # se mancano pacchetti, vengono installati
    if missing_packages:
        print(f"FaceMocap: Installazione automatica di {missing_packages}. Attendere...")
        subprocess.call([python_exe, "-m", "ensurepip"])
        subprocess.call([python_exe, "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.call([python_exe, "-m", "pip", "install", *missing_packages])
        print("FaceMocap: Installazione dipendenze completata.")

def register():
    install_dependencies()
    auto_load.register()

def unregister():
    auto_load.unregister()