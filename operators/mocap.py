from typing import Literal, NamedTuple

import bpy
from bpy.types import Context
from mathutils import Quaternion, Vector

from ..core import solver
from ..core import properties
from ..core import config
from ..core import rig
from ..core.retarget import RetargetSolver
from ..core.config import MappingRuntime, MotionMode, LandmarkSample, LANDMARKS_MAP, FACE_MAPPING, LANDMARKERS_FACE_MAPPING, LM_FOREHEAD, LM_NASION, LM_SIDE_L, LM_SIDE_R
from ..core.rig import find_rig, LANDMARKS_RIG_NAME
from ..core.webcam_core import FaceTracker
from .diagnostics import stampa_tabella_scale

TRACKED_INDICES = sorted(
    {data.landmark for data in FACE_MAPPING.values()}
    | {data.parent_landmark for data in FACE_MAPPING.values()
       if data.parent_landmark is not None}
    | {LM_SIDE_R, LM_SIDE_L, LM_FOREHEAD, LM_NASION}
)

ADVANCE_TRACKED_INDICES = sorted(
    {data.landmark for data in LANDMARKERS_FACE_MAPPING.values()}
    | {data.parent_landmark for data in LANDMARKERS_FACE_MAPPING.values()
       if data.parent_landmark is not None}
    | {LM_SIDE_R, LM_SIDE_L, LM_FOREHEAD, LM_NASION}
)

def _gain_gruppo(bone_name):
    """Moltiplicatore d'ampiezza del gruppo a cui l'osso appartiene."""
    if bone_name == "Jaw" or bone_name.startswith(("Lip_", "Mouth_")):
        return config.MOUTH_GAIN
    if bone_name.startswith(("Eye_", "Eyelid_")):
        return config.EYE_GAIN
    if bone_name.startswith("Brow_"):
        return config.BROW_GAIN
    return 1.0


class _Voce(NamedTuple):
    osso: str
    #Mediapipe relationship
    landmark: int
    genitore: int | None
    #Mirrored mediapipe relationship 
    landmark_speculare: int
    genitore_speculare: int
    gain: float               # gain per-osso gia' moltiplicato per quello di gruppo
    rotazione: bool           # osso a leva (mandibola) invece che in traslazione
    #type of motion
    motion_mode: MotionMode

#to review in way to adapt it for the advance_rig
def _piano_ossa(rig) -> list[_Voce]:
    voci = []
    if rig.name == LANDMARKS_RIG_NAME:
        mapping = LANDMARKERS_FACE_MAPPING
    else: 
        mapping = FACE_MAPPING

    for nome, data in mapping.items():
        speculare = mapping[solver.mirrored_bone_name(nome)]
        voci.append(_Voce(
            osso=nome,
            landmark=data.landmark,
            genitore=data.parent_landmark,
            landmark_speculare=speculare.landmark,
            genitore_speculare=speculare.parent_landmark,
            gain=data.gain * _gain_gruppo(nome),
            rotazione=nome in config.ROTATION_BONES,
            motion_mode= data.motion_mode
        ))
    return voci

def reset_rig_pose(rig):
    """Riporta a riposo le ossa gestite dal mocap.
       Reset the bone location position and rotation
    """
    if rig.name == LANDMARKS_RIG_NAME:
            mapping = LANDMARKERS_FACE_MAPPING
    else: 
        mapping = FACE_MAPPING

    for bone_name in mapping:
        pose_bone = rig.pose.bones.get(bone_name)
        if not pose_bone:
            continue
        pose_bone.location = (0.0, 0.0, 0.0)
        if pose_bone.rotation_mode == 'QUATERNION':
            pose_bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        else:
            pose_bone.rotation_euler = (0.0, 0.0, 0.0)

####################################################
#               Operators Classes                  #
####################################################
#added
class FACEMOCAP_OT_initialize(bpy.types.Operator):
    """Loads the default mapping"""
    bl_idname = "facemocap.initialize"
    bl_label = "Load Default Mapping"

    def execute(self, context: Context) -> set[Literal['RUNNING_MODAL'] | Literal['CANCELLED'] | Literal['FINISHED'] | Literal['PASS_THROUGH'] | Literal['INTERFACE']]:
        properties.populate_default_mapping(context.scene.facemocap)
        self.report({"INFO"}, "Default mapping loaded")

        return {"FINISHED"}

#To-do: review
class FACEMOCAP_OT_reset_pose(bpy.types.Operator):
    """Riporta l'armatura alla rest pose
       Reset pose to the default
    """
    bl_idname = "facemocap.reset_pose"
    bl_label = "Reset pose"
    bl_description = "Reset the pose to the default"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: bpy.types.Context) -> set[Literal['RUNNING_MODAL'] | Literal['CANCELLED'] | Literal['FINISHED'] | Literal['PASS_THROUGH'] | Literal['INTERFACE']]:
        rig = find_rig(context)
        if not rig:
            self.report({'ERROR'}, "Armatura FaceMocap not found.")
            return {'CANCELLED'}
        reset_rig_pose(rig)
        return {'FINISHED'}
#added
class FACEMOCAP_OT_validate(bpy.types.Operator):
    """Checks whether the mapping is valid for motion capture and applies it"""
    bl_idname = "facemocap.validate"
    bl_label = "validate Mapping"

    def execute(self, context) -> set[Literal['RUNNING_MODAL'] | Literal['CANCELLED'] | Literal['FINISHED'] | Literal['PASS_THROUGH'] | Literal['INTERFACE']]:
        settings = (context.scene.facemocap)
        target = rig.find_rig(context, settings.target_rig_name, target)

        if target is None:
            self.report({"ERROR"}, "Target rig not found")
            return {"CANCELLED"}

        missing = []

        for item in settings.mappings:
            if not item.enabled:
                continue
            if not item.target_bone:
                continue
            if(target.pose.bones.get(item.target_bone) is None):
                missing.append(item.target_bone)

        if missing:
            self.report({"WARNING"}, "Missing bones: " + ",".join(missing))
        else:
            self.report({"INFO"}, "Target mapping is valid")

        return {"FINISHED"}

class FACEMOCAP_OT_start_capture(bpy.types.Operator):
    """Avvia la motion capture facciale. ESC per fermare, C per ricalibrare
       Start the facial motion capture. Esc to stop, and C for recalibrating 
    """
    bl_idname = "facemocap.start_capture"
    bl_label = "Start Motion Capture"
    bl_description = "Creation of the armatrue for the motion capture"

    PIANO_OSSA: list[_Voce] = []
    _timer = None
    _tracker = None
    _area = None
    _rig = None
    _track_idx = TRACKED_INDICES
    _landmark_maps = LANDMARKS_MAP
    retarget = RetargetSolver()

    #added
    def configure(self, source_rig, target_rig, mappings):
        self.source_rig = source_rig
        self.target_rig = target_rig
        self.mappings = mappings

    #added
    def solve_source(self, landmarks, context: bpy.types.Context):
        settings = (context.scene.facemocap)
        frame = solver.build_head_frame(landmarks, aspect=settings.aspect_ratio)

        if frame is None:
            return None
        #it is possible improve it
        indices = {
            data.id_landmark
            for data in config.LANDMARKS_MAP.values()
        }

        local_by_index = (solver.to_head_local(landmarks, frame, indices, settings.aspect_ratio))

        local = {}

        for bone_name, data in config.LANDMARKS_MAP.items():
            ladnmarks_index = data.id_landmark
            local[bone_name] = (local_by_index[ladnmarks_index])

        return solver.SourcePose(
            local=local,
            origin=frame.origin,
            scale=frame.scale,
            head_rotation=frame.rotation
        )

    #added
    def apply_target(self, target_pose):
        if self.target_rig is None:
            return

        mapping_by_role = {mapping.role: mapping for mapping in self.mappings}

        for role, (mode, value) in target_pose.items():
            mapping = (mapping_by_role.get(role))

            if mapping is None:
                continue

            pose_bone = (self.target_rig.pose.bones.get(mapping.target_bone))

            if pose_bone is None:
                continue

            if mode == "TRANSLATION":
                rig.apply_rotation(pose_bone, value)
            elif mode == "ROTATION":
                rig.apply_rotation(pose_bone, value.to_matrix())

    #added
    def update(self, context):
        landmarks = (self.latest_landmarks)

        if landmarks is None:
            return

        source_pose = (self.solve_source(landmarks, context))

        if source_pose is None:
            return

        if self.retarget.neutral_head_rotation is None:
            return
        
        settings = (context.scene.facemocap)
        target_pose = (self.retarget.solve(source_pose, self.mappings, settings.smoothing, settings.mirror_x))

        self.apply_target(target_pose)

    #move to retarget class
    def _begin_calibration(self, context: bpy.types.Context) -> None:
        """Azzera la posa e riparte a raccogliere la posa neutra."""
        self._calib_left = config.CALIBRATION_FRAMES
        self._calib_sum = {}
        self._calib_origin = Vector((0.0, 0.0, 0.0))
        self._calib_scale = 0.0
        self._calib_quats = []

        self._neutral = None
        self._unit_scale = None
        self._bone_scales = {}
        self._smoothed = {}
        self._smoothed_rot = {}
        self._warned_bones = set()
        self._smoothed_quat = Quaternion((1.0, 0.0, 0.0, 0.0))

        reset_rig_pose(self._rig)

    #move to retarget class
    def _accumulate_calibration(self, local, origin, rot, scale) -> None:
        for idx, vec in local.items():
            if idx in self._calib_sum:
                self._calib_sum[idx] += vec
            else:
                self._calib_sum[idx] = vec.copy()

        self._calib_origin += origin
        self._calib_scale += scale

        quat = rot.to_quaternion()
        if self._calib_quats and quat.dot(self._calib_quats[0]) < 0.0:
            quat.negate()
        self._calib_quats.append(quat)

        self._calib_left -= 1

    #move to retarget class
    def _finish_calibration(self, context: bpy.types.Context) -> bool:
        count = len(self._calib_quats)
        if count == 0:
            return False

        self._neutral = {idx: vec / count for idx, vec in self._calib_sum.items()}
        self._neutral_origin = self._calib_origin / count
        self._neutral_scale = self._calib_scale / count

        avg = Quaternion((0.0, 0.0, 0.0, 0.0))
        for quat in self._calib_quats:
            avg.w += quat.w
            avg.x += quat.x
            avg.y += quat.y
            avg.z += quat.z
        avg.normalize()
        self._neutral_rot = avg.to_matrix()

        dett_unit = {}
        self._unit_scale = solver.solve_unit_scale(self._rig, self._neutral, dett_unit)
        if self._unit_scale is None:
            #self.report({'WARNING'}, "Impossibile stimare la scala del rig: controlla le posizioni delle ossa.")
            self.report({'WARNING'}, "Unable to estimate rig's scale: check the bones' postions.")
            return False
        
        dett_scale = {}
        self._bone_scales = solver.solve_bone_scales(
            self._rig, self._neutral, self._unit_scale, dett_scale
        )

        stampa_tabella_scale(self._unit_scale, dett_unit, dett_scale)

        #self.report({'INFO'}, "Calibrato. Scala rig: %.4f unita' per larghezza "
        #            "viso. Tabella delle scale nella console di sistema."
        #            % self._unit_scale)
                    
        self.report({'INFO'}, "Calibrated. Rig's scale: %.4f unit per width"
                    "face. Table scale on console."
                    % self._unit_scale)

        return True

    def _solve_landmark_pose(self, local, scale, settings):
        result = {}

        for mapping in self._landmark_maps.values():
            pose_bone = self._rig.pose.bones.get(mapping.bone)

            if pose_bone is None:
                continue

            delta = self._landmark_delta(mapping.landmark, local)

            if delta is None:
                continue

            result[mapping.bone] = LandmarkPose(location=solver.head_local_to_blender(delta, settings.mirror_x), rotation=None)

        return result

    def _retarget_pose(self, source_pose, settings):
        result = {}

        for mapping in self._retarget_maps:
            if mapping.mode == MotionMode.TRANSLATION:
                result[mapping.target] = self._retarget_translation(mapping, source_pose)
            elif mapping.mode == MotionMode.ROTATION:
                result[mapping.target] = self._retarget_rotation(mapping, source_pose)
            elif mapping.mode == MotionMode.AIM:
                result[mapping.target] = self._retarget_aim(mapping, source_pose)

        return result


    #modified
    def _apply_pose(self, context: bpy.types.Context, local, origin, rot, scale):
        settings = context.scene.facemocap

        #solve source landmark skeleton
        source_pose = self._solve_landmark_pose(local=local, scale=scale, settings=settings)
        #retarget
        target_pose = self._retarget_pose(source_pose=source_pose, settings=settings)
        #apply target pose
        self._apply_target_pose(target_pose, alpha=1.0 - config.SMOOTHING)

    def _warn_bad_lever(self, bone_name):
        """Avvisa una sola volta che l'osso non e' orientato come una leva.
        
        """
        if bone_name in self._warned_bones:
            return
        self._warned_bones.add(bone_name)
        self.report(
            {'WARNING'},
            "Osso '%s': la coda deve stare sul MENTO e la testa "
            "sull'articolazione vicino all'orecchio. Ora punta verso l'alto, "
            "quindi uso la traslazione. Rigenera l'armatura o riposiziona l'osso."
            % bone_name,
        )

    def _apply_lever_rotation(self, pose_bone, bone_name, tip_delta, alpha) -> bool:
        """Applica a un osso a leva (la mandibola) la rotazione corrispondente."""
        armature_rot = solver.solve_rotation_from_lever(pose_bone, tip_delta)
        if armature_rot is None:
            return False

        bone_rot = solver.rotation_to_bone_space(pose_bone, armature_rot)
        quat = bone_rot.to_quaternion()

        previous = self._smoothed_rot.get(bone_name)
        quat = quat if previous is None else previous.slerp(quat, alpha)
        self._smoothed_rot[bone_name] = quat

        if pose_bone.rotation_mode != 'QUATERNION':
            pose_bone.rotation_mode = 'QUATERNION'
        pose_bone.rotation_quaternion = quat
        return True

    def _solve_head_translation(self, settings, origin, scale):
        """Spostamento della testa nello spazio, in unita' armatura."""
        #diviso per la scala corrente quindi il risultato e' "quante larghezze di
        # viso si e' spostata la testa", quindi indipendente dalla distanza.
        offset = (origin - self._neutral_origin) / scale

        depth = (self._neutral_scale / scale - 1.0) * config.HEAD_DEPTH_GAIN

        vec = Vector((offset.x, depth, -offset.y))
        if settings.mirror_x:
            vec.x = -vec.x
        return vec * (self._unit_scale * config.HEAD_GAIN)


    def _apply_head_rotation(self, context, rot, alpha):
        pose_bone = self._rig.pose.bones.get("Head")
        if not pose_bone:
            return

        settings = context.scene.facemocap
        armature_rot = solver.head_rotation_matrix(self._neutral_rot, rot)
        if settings.mirror_x:
            armature_rot = solver.mirror_rotation(armature_rot)
        bone_rot = solver.rotation_to_bone_space(pose_bone, armature_rot)

        quat = bone_rot.to_quaternion()
        if abs(config.HEAD_GAIN - 1.0) > 1e-6:
            axis, angle = quat.to_axis_angle()
            quat = Quaternion(axis, angle * config.HEAD_GAIN)

        self._smoothed_quat = self._smoothed_quat.slerp(quat, alpha)

        if pose_bone.rotation_mode != 'QUATERNION':
            pose_bone.rotation_mode = 'QUATERNION'
        pose_bone.rotation_quaternion = self._smoothed_quat

    #Handle the keywork events for the motion capture
    def modal(self, context: bpy.types.Context, event: bpy.types.Event) -> set[Literal['RUNNING_MODAL'] | Literal['CANCELLED'] | Literal['FINISHED'] | Literal['PASS_THROUGH'] | Literal['INTERFACE']]:
        """Handel the keywork events for the motion capture"""
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'C' and event.value == 'PRESS':
            self._begin_calibration(context)
            #self._set_header(context, "Ricalibrazione: mantieni il viso neutro")
            self._set_header(context, "Recalibrating: keep a relaxed facial expression.")
            return {'RUNNING_MODAL'}

        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        
        #reading landmarks information
        results = self._tracker.read_landmarks()
        if results is None:
            return {'PASS_THROUGH'}
        landmarks, aspect = results
        #ok
        head_frame = solver.build_head_frame(landmarks, aspect)
        if head_frame is None:
            return {'PASS_THROUGH'}
        origin, rot, scale = head_frame
        #ok
        local = solver.to_head_local(landmarks, self._track_idx, origin, rot, scale, aspect)
        #added: landmark sample concept
        samples = {}

        for idx, curr in local.items():
            neutral = self._neutral.get(idx)

            if neutral is None:
                continue

            samples[idx] = LandmarkSample(
                idx=idx,
                pos=curr,
                neutral_pos=neutral,
                delta=curr - neutral
            )

        if self._neutral is None:
            self._accumulate_calibration(local, origin, rot, scale)
            if self._calib_left > 0:
                self._set_header(context, "keep a relaxed facial expression.... %d" % self._calib_left)
            elif not self._finish_calibration(context):
                self.cancel(context)
                return {'CANCELLED'}
            else:
                self._set_header(context, "Mocap actived | ESC = stop | C = Ricalibration")
        else:
            #to see
            self._apply_pose(context, local, origin, rot, scale)

        #to see
        if self._area:
            self._area.tag_redraw()

        return {'PASS_THROUGH'}

    def _set_header(self, context, text) -> None:
        if self._area:
            self._area.header_text_set("FaceMocap: " + text)

    def _get_track_index(self, rig):
        if rig.name == LANDMARKS_RIG_NAME:
            return ADVANCE_TRACKED_INDICES
        return TRACKED_INDICES

    def execute(self, context: bpy.types.Context) -> set[Literal['RUNNING_MODAL'] | Literal['CANCELLED'] | Literal['FINISHED'] | Literal['PASS_THROUGH'] | Literal['INTERFACE']]:
        settings = (context.scene.facemocap)
        #now is necessary to check the source and target rig
        self._rig = find_rig(context)
        #self._track_idx = self._get_track_index(self._rig)
        #FACEMOCAP_OT_start_capture.PIANO_OSSA = _piano_ossa(self._rig)
        
        if not self._rig:
            self.report({'ERROR'}, "FaceMocap rig not found. Generate it before starting.")
            return {'CANCELLED'}

        if properties.mapping_is_empty(settings):
            properties.populate_default_mapping(settings)
            
        mappings = []

        for item in settings.mappings:
            source_bones = tuple(name.strip() for name in item.source_bones.split(",") if name.strip())
            mappings.append(
                MappingRuntime(
                    role=item.role,
                    target=item.target_bone,
                    source=source_bones,
                    mode=item.mode,
                    gain=item.gain,
                    enable=item.enabled
                )
            )
        self._tracker = FaceTracker()
        if not self._tracker.start():
            self.report({'ERROR'}, "Unable to start the webcam.")
            return {'CANCELLED'}

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        self._rig.select_set(True)
        context.view_layer.objects.active = self._rig
        bpy.ops.object.mode_set(mode='POSE')

        self._area = context.area if context.area and context.area.type == 'VIEW_3D' else None
        #we should use the retarget for the calibration
        self._begin_calibration(context)
        self._set_header(context, "keep a relaxed facial expression...")

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.03, window=context.window)
        wm.modal_handler_add(self)

        self.report({'INFO'}, "Motion Capture started. Press ESC to stop, C to recalibrate.")
        return {'RUNNING_MODAL'}

    def cancel(self, context: bpy.types.Context) -> None:
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
            self._timer = None
        if self._tracker:
            self._tracker.stop()
            self._tracker = None
        if self._area:
            self._area.header_text_set(None)
            self._area = None
        self.report({'INFO'}, "Motion Capture stopped.")

#added: calculate position and place in the blender space the marker bone associated to the landmark 
def _solve_landmark_bone(self, pose_bone, landmark_delta, scale):
    target = solver.head_local_to_blender(landmark_delta, self._settigns.mirror_x)
    target *= scale * config.AMPLITUDE
    pose_bone.location = solver.to_bone_space(pose_bone, target)