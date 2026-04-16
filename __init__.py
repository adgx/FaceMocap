bl_info = {
    "name": "FaceMocap",
    "author": "adgx and F3de22",
    "blender": (2, 80, 0),
    "category": "Animation",
}

from . import auto_load

auto_load.init()

def register():
    auto_load.register()

def unregister():
    auto_load.unregister()