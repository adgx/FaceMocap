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
if str(LIB_DIR) not in sys.path:
    sys.path.append(str(LIB_DIR))
 
 
def _run(cmd):
    print(f"FaceMocap: eseguo -> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode != 0:
        print(f"FaceMocap: ATTENZIONE, comando fallito con codice {result.returncode}: {' '.join(cmd)}")
    return result.returncode == 0

#installa le dipendenze se non sono già installate
def install_dependencies():
    python_exe = sys.executable
    print(f"FaceMocap: uso l'interprete Python -> {python_exe}")
    print(f"FaceMocap: cartella dipendenze locali -> {LIB_DIR}")
    missing_packages = []
 
    try:
        import cv2
        print("FaceMocap: cv2 già presente, versione", cv2.__version__)
    except ImportError as e:
        print(f"FaceMocap: cv2 non trovato ({e})")
        missing_packages.append("opencv-python==4.9.0.80")
 
    try:
        import mediapipe
        print("FaceMocap: mediapipe già presente, versione", mediapipe.__version__)
    except ImportError as e:
        print(f"FaceMocap: mediapipe non trovato ({e})")
        missing_packages.append("mediapipe==0.10.11")
 
    if missing_packages:
        print(f"FaceMocap: Installazione automatica di {missing_packages} in {LIB_DIR}. Attendere...")
        ok = _run([python_exe, "-m", "ensurepip"])
        ok = _run([python_exe, "-m", "pip", "install", "--upgrade", "pip"]) and ok
        ok = _run([
            python_exe, "-m", "pip", "install",
            "--target", str(LIB_DIR),
            "numpy<2", "protobuf<4", *missing_packages,
        ]) and ok
 
        if not ok:
            print("FaceMocap: ERRORE - uno o più comandi di installazione sono falliti. Vedi output sopra.")
        else:
            print("FaceMocap: Installazione dipendenze completata con successo.")
 
        importlib.invalidate_caches()
 
        for pkg_import, pkg_name in [("cv2", "opencv-python"), ("mediapipe", "mediapipe")]:
            try:
                importlib.import_module(pkg_import)
                print(f"FaceMocap: verifica OK, '{pkg_import}' importabile dopo l'installazione.")
            except ImportError as e:
                print(f"FaceMocap: verifica FALLITA per '{pkg_import}' ({pkg_name}): {e}")

def register():
    install_dependencies()
    auto_load.init()
    auto_load.register()

def unregister():
    from . import auto_load
    auto_load.unregister()