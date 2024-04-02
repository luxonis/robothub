import logging
import os
import pathlib
import threading
import time
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum, auto
from typing import List, Optional, Tuple

import cv2
import depthai as dai
import numpy as np

import robothub as rh

# TODO(miha):
#   - pause toggle (when paused we don't read video)
#   - should we use img_manip node to resize preview or cv2?
#   - get actual sizes for raw, isp
#   - test loop=False


class PathType(Enum):
    VIDEO = auto()
    IMAGE_DIRECTORY = auto()


@dataclass
class StreamName:
    suffix: str
    INPUT_CONTROL: str = field(init=False)
    INPUT_CONFIG: str = field(init=False)
    GRAY: str = field(init=False)
    RAW: str = field(init=False)
    ISP: str = field(init=False)
    VIDEO: str = field(init=False)
    STILL: str = field(init=False)
    PREVIEW: str = field(init=False)

    def __post_init__(self):
        self.INPUT_CONTROL = f"rh_replay_input_control_{self.suffix}"
        self.INPUT_CONFIG = f"rh_replay_input_config_{self.suffix}"
        self.GRAY = f"rh_replay_gray_{self.suffix}"
        self.RAW = f"rh_replay_raw_{self.suffix}"
        self.ISP = f"rh_replay_isp_{self.suffix}"
        self.VIDEO = f"rh_replay_video_{self.suffix}"
        self.STILL = f"rh_replay_still_{self.suffix}"
        self.PREVIEW = f"rh_replay_preview_{self.suffix}"


class ImageDirectoryCapture:
    """
    Used for sending images from directory to the replay node instead of a video.
    """

    def __init__(self, path: pathlib.Path):
        image_files = [
            os.path.join(str(path), f) for f in os.listdir(str(path)) if f.endswith((".png", ".jpg", ".jpeg"))
        ]
        image_files.sort()
        self.image_files = image_files
        self.current_frame = 0

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self.current_frame < len(self.image_files):
            frame = cv2.imread(self.image_files[self.current_frame])
            self.current_frame += 1
            return True, frame
        else:
            return False, None

    def reset(self):
        self.current_frame = 0

    def isOpened(self):
        return True

    def release(self):
        pass


# from https://github.com/opencv/opencv/issues/21727#issuecomment-1068908078
def BGR2YUV_NV12(src):
    src_h, src_w = src.shape[:2]
    # Convert BGR to YUV_I420
    dst = cv2.cvtColor(src, cv2.COLOR_BGR2YUV_I420)
    n_y = src_h * src_w
    n_uv = n_y // 2
    n_u = n_y // 4

    # Extract the Y plane
    y_plane = dst[:src_h].reshape((src_h, src_w))

    # Extract the U and V planes, then interleave them for NV12 format
    u_plane = dst[src_h : src_h + src_h // 4].reshape((-1, src_w // 2))
    v_plane = dst[src_h + src_h // 4 :].reshape((-1, src_w // 2))

    uv_plane = np.zeros((src_h // 2, src_w), dtype=np.uint8)
    uv_plane[:, 0::2] = u_plane.reshape((-1, src_w // 2))
    uv_plane[:, 1::2] = v_plane.reshape((-1, src_w // 2))

    # Combine Y and interleaved UV planes into one NV12 image
    nv12_img = np.vstack((y_plane, uv_plane)).astype(np.uint8)
    return nv12_img


def to_planar(arr: np.ndarray, shape: tuple) -> np.ndarray:
    return cv2.resize(arr, shape).transpose(2, 0, 1).flatten()


class ReplayCamera:
    replay_camera_instances: list['ReplayCamera'] = []

    def __init__(self, pipeline: dai.Pipeline, fps: float, src: str, run_in_loop: bool = True):
        self.replay_camera_instances.append(self)
        self._stream_name: StreamName = StreamName(suffix=str(len(self.replay_camera_instances)))
        # NOTE(miha): Replay node inputs/outputs
        self._input_control: Optional[dai.Node.Input] = None
        self._input_config: Optional[dai.Node.Input] = None
        self._raw: Optional[dai.Node.Output] = None
        self._isp: Optional[dai.Node.Output] = None
        self._video: Optional[dai.Node.Output] = None
        self._still: Optional[dai.Node.Output] = None
        self._preview: Optional[dai.Node.Output] = None
        self._out: Optional[dai.Node.Output] = None
        # self.frameEvent: Optional[dai.Node.Output] = None
        # self.InitialControl: Optional[dai.CameraControl] = None

        self._input_control_queue: Optional[dai.DataOutputQueue] = None
        self._input_config_queue: Optional[dai.DataOutputQueue] = None
        self._raw_queue: Optional[dai.DataInputQueue] = None
        self._isp_queue: Optional[dai.DataInputQueue] = None
        self._video_queue: Optional[dai.DataInputQueue] = None
        self._still_queue: Optional[dai.DataInputQueue] = None
        self._preview_queue: Optional[dai.DataInputQueue] = None
        self._out_queue: Optional[dai.DataOutputQueue] = None

        self._fps: float = fps
        self._video_width: int = 1920
        self._video_height: int = 1080
        self._preview_width: int = 1280
        self._preview_height: int = 720
        self._color_order: dai.ColorCameraProperties.ColorOrder = dai.ColorCameraProperties.ColorOrder.BGR
        self._interleaved = False
        self._run_in_loop = run_in_loop
        self._pipeline: dai.Pipeline = pipeline
        self._camera_socket: dai.CameraBoardSocket | None = None

        self._init_cap(src)
        if self._cap is None:
            logging.error("Couldn't init the cap")
            return

        # NOTE(miha): Used for saving references to nodes if we want to set max
        # data size later (i.e. calling setPreviewSize also alter max data size).
        self._nodes = {}

    def _parse_src(self, src: str) -> Optional[pathlib.Path]:
        path = pathlib.Path(src).resolve()
        if path.is_file():
            self._path_type = PathType.VIDEO
            return path
        elif path.is_dir():
            self._path_type = PathType.IMAGE_DIRECTORY
            return path
        else:
            logging.error(f"provided file: {src} is not a file or not a dir")

    def _init_cap(self, src: str):
        self._path_type: PathType
        self._path = self._parse_src(src)
        if self._path is None:
            logging.error(f"Error in parsing src: {src}")
            return

        if self._path_type == PathType.VIDEO:
            self._cap = cv2.VideoCapture(str(self._path))
        else:
            self._cap = ImageDirectoryCapture(self._path)  # type: ignore

    def _reset_cap(self):
        self._cap.release()
        if self._path_type == PathType.VIDEO:
            self._cap = cv2.VideoCapture(str(self._path))
        else:
            self._cap.reset()  # type:ignore

    def _create_cam_input(self, pipeline: dai.Pipeline, stream_name: str):
        node = pipeline.createXLinkOut()
        node.setStreamName(stream_name)
        self._nodes[stream_name] = node
        return node.input

    def _create_cam_output(self, pipeline: dai.Pipeline, stream_name: str, max_data_size: int | None = None):
        node = pipeline.create(dai.node.XLinkIn)
        node.setStreamName(stream_name)
        if max_data_size is not None:
            node.setMaxDataSize(max_data_size)
        self._nodes[stream_name] = node
        return node.out

    def _send_video_frames(self, device: dai.Device):
        if self._input_control is not None:
            self._input_control_queue = device.getOutputQueue(name=self._stream_name.INPUT_CONTROL)
        if self._input_config is not None:
            self._input_config_queue = device.getOutputQueue(name=self._stream_name.INPUT_CONFIG)

        if self._raw is not None:
            self._raw_queue = device.getInputQueue(name=self._stream_name.RAW)
        if self._isp is not None:
            self._isp_queue = device.getInputQueue(name=self._stream_name.ISP)
        if self._video is not None:
            self._video_queue = device.getInputQueue(name=self._stream_name.VIDEO)
        if self._still is not None:
            self._still_queue = device.getInputQueue(name=self._stream_name.STILL)
        if self._preview is not None:
            self._preview_queue = device.getInputQueue(name=self._stream_name.PREVIEW)
        if self._out is not None:
            self._out_queue = device.getInputQueue(name=self._stream_name.GRAY)

        sequence_number = 0
        send_video_frames_start = time.time()

        def create_img_frame(
            data: np.ndarray,
            width: int,
            height: int,
            type: dai.RawImgFrame.Type,
            sequence_number: int,
            timestamp: timedelta,
        ):
            img_frame = dai.ImgFrame()
            img_frame.setType(type)
            img_frame.setData(data.flatten())
            img_frame.setTimestamp(timestamp)
            img_frame.setSequenceNum(sequence_number)
            img_frame.setWidth(width)
            img_frame.setHeight(height)
            if self._camera_socket is not None:
                img_frame.setInstanceNum(int(self._camera_socket))
            return img_frame

        def get_next_frame():
            if not self._cap.isOpened():
                return None

            frame = None
            for _ in range(2):
                next_frame_exists, frame = self._cap.read()
                if not next_frame_exists and self._run_in_loop:
                    self._reset_cap()
                    continue
                break

            return frame

        while rh.app_is_running:
            start = time.monotonic()

            # NOTE(miha): Returned frame is in BGR format
            frame = get_next_frame()
            if frame is None:
                break

            timestamp: timedelta = timedelta(seconds=time.time() - send_video_frames_start)

            # NOTE(miha): Mock input control commands
            if self._input_control_queue is not None:
                if self._input_control_queue.has():
                    ctrl: dai.CameraControl = self._input_control_queue.get()  # type: ignore

                    # TODO(miha): Send image to still queue
                    if ctrl.getCaptureStill():
                        pass
            if self._input_config_queue is not None:
                pass

            if self._raw_queue is not None:
                self._raw_queue.send(dai.ImgFrame())
            if self._isp_queue is not None:
                self._isp_queue.send(dai.ImgFrame())
            if self._video_queue is not None:
                nv12_frame = BGR2YUV_NV12(frame)
                video_img_frame = create_img_frame(
                    data=nv12_frame,
                    width=self._video_width,
                    height=self._video_height,
                    type=dai.ImgFrame.Type.NV12,
                    sequence_number=sequence_number,
                    timestamp=timestamp,
                )
                self._video_queue.send(video_img_frame)
            if self._still_queue is not None:
                self._still_queue.send(dai.ImgFrame())
            if self._preview_queue is not None or self._out_queue is not None:
                preview_frame = cv2.resize(frame, (self._preview_width, self._preview_height))
                preview_img_frame = create_img_frame(
                    data=to_planar(preview_frame, (self._preview_width, self._preview_height)),
                    width=self._preview_width,
                    height=self._preview_height,
                    type=dai.ImgFrame.Type.BGR888p,
                    sequence_number=sequence_number,
                    timestamp=timestamp,
                )
                if self._preview_queue is not None:
                    self._preview_queue.send(preview_img_frame)
                if self._out_queue is not None:
                    self._out_queue.send(preview_img_frame)

            sequence_number += 1

            process_time = time.monotonic() - start
            if process_time > 1. / self._fps:
                logging.error(
                    f"Proccessing time ({process_time:.3f}ms) didn't hit the set camera FPS deadline ({1. / self._fps:.3f}ms)"
                )
            time_to_sleep = max((1. / self._fps) - process_time, 0)
            logging.debug(f"process_time: {process_time}, time_to_sleep: {time_to_sleep}")
            time.sleep(time_to_sleep)

        self._cap.release()

    def start_polling(self, device: dai.Device):
        thread = threading.Thread(target=self._send_video_frames, args=(device,))
        thread.start()

    # NOTE(miha): Below are methods for ColorCamera class:

    def getBoardSocket(self) -> dai.CameraBoardSocket:
        return self._camera_socket

    def getCamId(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def getCamera(self) -> str:
        raise NotImplementedError("This function is not yet implemented")

    def getColorOrder(self) -> dai.ColorCameraProperties.ColorOrder:
        return self._color_order

    def getFp16(self) -> bool:
        raise NotImplementedError("This function is not yet implemented")

    def getFps(self) -> float:
        return self._fps

    def getFrameEventFilter(self) -> List[dai.FrameEvent]:
        raise NotImplementedError("This function is not yet implemented")

    def getImageOrientation(self) -> dai.CameraImageOrientation:
        raise NotImplementedError("This function is not yet implemented")

    def getInterleaved(self) -> bool:
        return self._interleaved

    def getIspHeight(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def getIspSize(self) -> Tuple[int, int]:
        raise NotImplementedError("This function is not yet implemented")

    def getIspWidth(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def getPreviewHeight(self) -> int:
        return self._preview_height

    def getPreviewKeepAspectRatio(self) -> bool:
        raise NotImplementedError("This function is not yet implemented")

    def getPreviewNumFramesPool(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def getPreviewSize(self) -> Tuple[int, int]:
        return (self._preview_width, self._preview_height)

    def getPreviewWidth(self) -> int:
        return self._preview_width

    def getRawNumFramesPool(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def getResolution(self) -> dai.ColorCameraProperties.SensorResolution:
        raise NotImplementedError("This function is not yet implemented")

    def getResolutionHeight(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def getResolutionSize(self) -> Tuple[int, int]:
        raise NotImplementedError("This function is not yet implemented")

    def getResolutionWidth(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def getSensorCrop(self) -> Tuple[float, float]:
        raise NotImplementedError("This function is not yet implemented")

    def getSensorCropX(self) -> float:
        raise NotImplementedError("This function is not yet implemented")

    def getSensorCropY(self) -> float:
        raise NotImplementedError("This function is not yet implemented")

    def getStillHeight(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def getStillNumFramesPool(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def getStillSize(self) -> Tuple[int, int]:
        raise NotImplementedError("This function is not yet implemented")

    def getStillWidth(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def getVideoHeight(self) -> int:
        return self._video_height

    def getVideoNumFramesPool(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def getVideoSize(self) -> Tuple[int, int]:
        return (self._video_width, self._video_height)

    def getVideoWidth(self) -> int:
        return self._video_width

    def getWaitForConfigInput(self) -> bool:
        raise NotImplementedError("This function is not yet implemented")

    def sensorCenterCrop(self) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setBoardSocket(self, boardSocket: dai.CameraBoardSocket) -> None:
        self._camera_socket = boardSocket

    def setCamId(self, arg0: int) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setCamera(self, name: str) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setColorOrder(self, colorOrder: dai.ColorCameraProperties.ColorOrder) -> None:
        self._color_order = colorOrder

    def setFp16(self, fp16: bool) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setFps(self, fps: float) -> None:
        self._fps = fps

    def setFrameEventFilter(self, events: List[dai.FrameEvent]) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setImageOrientation(self, imageOrientation: dai.CameraImageOrientation) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setInterleaved(self, interleaved: bool) -> None:
        self._interleaved = interleaved

    def setIsp3aFps(self, arg0: int) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setIspNumFramesPool(self, arg0: int) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setIspScale(self, numerator: int, denominator: int) -> None:
        raise NotImplementedError("This function is not yet implemented")

    # @overload
    # def setIspScale(self, numerator: int, denominator: int) -> None:
    #
    # @overload
    # def setIspScale(self, scale: Tuple[int, int]) -> None:
    #
    # @overload
    # def setIspScale(self, horizNum: int, horizDenom: int, vertNum: int, vertDenom: int) -> None:
    #
    # @overload
    # def setIspScale(self, horizScale: Tuple[int, int], vertScale: Tuple[int, int]) -> None:

    def setNumFramesPool(self, raw: int, isp: int, preview: int, video: int, still: int) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setPreviewKeepAspectRatio(self, keep: bool) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setPreviewNumFramesPool(self, arg0: int) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setPreviewSize(self, width: int, height: int) -> None:
        self.preview  # Ensures that 'preview' is inited (lazy loaded).
        self._preview_width = width
        self._preview_height = height
        self._nodes[self._stream_name.PREVIEW].setMaxDataSize(width * height * 3)

    # @overload
    # def setPreviewSize(self, width: int, height: int) -> None:
    #     raise NotImplementedError("This function is not yet implemented")
    #
    # @overload
    # def setPreviewSize(self, size: Tuple[int, int]) -> None:
    #     raise NotImplementedError("This function is not yet implemented")

    def setRawNumFramesPool(self, arg0: int) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setRawOutputPacked(self, packed: bool) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setResolution(self, resolution: dai.ColorCameraProperties.SensorResolution) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setSensorCrop(self, x: float, y: float) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setStillNumFramesPool(self, arg0: int) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setStillSize(self, width: int, height: int) -> None:
        raise NotImplementedError("This function is not yet implemented")

    # @overload
    # def setStillSize(self, width: int, height: int) -> None:
    #     raise NotImplementedError("This function is not yet implemented")
    #
    # @overload
    # def setStillSize(self, size: Tuple[int, int]) -> None:
    #     raise NotImplementedError("This function is not yet implemented")

    def setVideoNumFramesPool(self, arg0: int) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setVideoSize(self, width: int, height: int) -> None:
        self.video  # Ensures that 'video' is inited (lazy loaded).
        self._video_width = width
        self._video_height = height
        self._nodes[self._stream_name.VIDEO].setMaxDataSize(width * height * 3)

    # @overload
    # def setVideoSize(self, width: int, height: int) -> None:
    #     raise NotImplementedError("This function is not yet implemented")
    #
    # @overload
    # def setVideoSize(self, size: Tuple[int, int]) -> None:
    #     raise NotImplementedError("This function is not yet implemented")

    def setWaitForConfigInput(self, wait: bool) -> None:
        raise NotImplementedError("This function is not yet implemented")

    @property
    def frameEvent(self) -> dai.Node.Output:
        raise NotImplementedError("This function is not yet implemented")

    @property
    def initialControl(self) -> dai.CameraControl:
        raise NotImplementedError("This function is not yet implemented")

    @property
    def inputConfig(self) -> dai.Node.Input:
        if self._input_config is None:
            self._input_config = self._create_cam_input(self._pipeline, self._stream_name.INPUT_CONFIG)
        return self._input_config

    @property
    def inputControl(self) -> dai.Node.Input:
        if self._input_control is None:
            self._input_control = self._create_cam_input(self._pipeline, self._stream_name.INPUT_CONTROL)
        return self._input_control

    @property
    def isp(self) -> dai.Node.Output:
        if self._isp is None:
            self._isp = self._create_cam_output(self._pipeline, self._stream_name.ISP)
        return self._isp

    @property
    def preview(self) -> dai.Node.Output:
        if self._preview is None:
            self._preview = self._create_cam_output(self._pipeline, self._stream_name.PREVIEW)
        return self._preview

    @property
    def raw(self) -> dai.Node.Output:
        if self._raw is None:
            self._raw = self._create_cam_output(self._pipeline, self._stream_name.RAW)
        return self._raw

    @property
    def still(self) -> dai.Node.Output:
        if self._still is None:
            self._still = self._create_cam_output(self._pipeline, self._stream_name.STILL)
        return self._still

    @property
    def video(self) -> dai.Node.Output:
        if self._video is None:
            self._video = self._create_cam_output(self._pipeline, self._stream_name.VIDEO)
        return self._video

    @property
    def out(self) -> dai.Node.Output:
        if self._out is None:
            node_out = self._create_cam_output(self._pipeline, self._stream_name.GRAY)
            manip = self._pipeline.createImageManip()
            manip.setFrameType(dai.RawImgFrame.Type.RAW8)
            manip.setResize(1280, 800)
            manip.setKeepAspectRatio(False)
            node_out.link(manip.inputImage)
            self._out = manip.out
        return self._out
