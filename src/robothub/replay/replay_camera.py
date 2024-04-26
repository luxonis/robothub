import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import timedelta
from typing import List, Optional, Tuple

import cv2
import depthai as dai

import robothub as rh
from robothub.replay.capture_manager import CaptureManager
from robothub.replay.utils import BGR2YUV_NV12, create_img_frame, to_planar

__all__ = ["ReplayCamera", "ColorReplayCamera", "MonoReplayCamera"]


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


class ReplayCamera(ABC):
    replay_camera_instances: list["ReplayCamera"] = []

    @abstractmethod
    def _send_video_frames(self, device: dai.Device):
        pass

    @abstractmethod
    def start_polling(self, device: dai.Device):
        pass

    @abstractmethod
    def stop_polling(self):
        pass

    @property
    @abstractmethod
    def replay_is_running(self) -> bool:
        pass


class ColorReplayCamera(ReplayCamera):
    def __init__(
            self,
            pipeline: dai.Pipeline,
            fps: float,
            src: str | List[str],
            run_in_loop: bool = True,
            start: Optional[int] = None,
            end: Optional[int] = None,
    ):
        super().__init__()
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
        # self.frameEvent: Optional[dai.Node.Output] = None
        # self.InitialControl: Optional[dai.CameraControl] = None

        self._input_control_queue: Optional[dai.DataOutputQueue] = None
        self._input_config_queue: Optional[dai.DataOutputQueue] = None
        self._raw_queue: Optional[dai.DataInputQueue] = None
        self._isp_queue: Optional[dai.DataInputQueue] = None
        self._video_queue: Optional[dai.DataInputQueue] = None
        self._still_queue: Optional[dai.DataInputQueue] = None
        self._preview_queue: Optional[dai.DataInputQueue] = None

        self._fps: float = fps
        self._start = start
        self._end = end
        self._run_in_loop = run_in_loop
        self._pipeline: dai.Pipeline = pipeline

        self._video_width: int = 1920
        self._video_height: int = 1080
        self._preview_width: int = 1280
        self._preview_height: int = 720
        self._preview_crop_needed: Optional[bool] = None
        self._preview_x_coords: Optional[tuple[int, int]] = None
        self._isp_width: int = 1920
        self._isp_height: int = 1080
        self._raw_width: int = 1280
        self._raw_height: int = 720
        self._still_width: int = 1280
        self._still_height: int = 720
        self._color_order: dai.ColorCameraProperties.ColorOrder = dai.ColorCameraProperties.ColorOrder.BGR
        self._interleaved = False
        self._camera_socket: dai.CameraBoardSocket | None = None

        self._send_capture_still: bool = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        if isinstance(src, str):
            src = [src]

        self._capture_manager = CaptureManager(src, self._run_in_loop, self._start, self._end)

        # NOTE(miha): Used for saving references to nodes if we want to set max
        # data size later (i.e. calling setPreviewSize also alter max data size).
        self._nodes = {}

    def get_capture_manager(self) -> CaptureManager:
        return self._capture_manager

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

    def _use_nv12_frame(self) -> bool:
        return self._video_queue is not None or self._still_queue is not None or self._isp_queue is not None

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

        sequence_number = 0
        send_video_frames_start = time.time()

        while rh.app_is_running() and self.replay_is_running:
            start = time.monotonic()

            # NOTE(miha): Returned frame is in BGR format
            frame = self._capture_manager.get_next_frame()
            if frame is None:
                break

            frame_h, frame_w = frame.shape[:2]
            if self._isp_width > frame_w or self._isp_height > frame_h:
                logging.error(f"ISP frame size ({self._isp_width}x{self._isp_height}) is bigger than source frame size ({frame_w}x{frame_h})."
                              f" Setting ISP size to frame size.")
                self._isp_width = frame_w
                self._isp_height = frame_h
            if self._raw_width > frame_w or self._raw_height > frame_h:
                logging.error(f"RAW frame size ({self._raw_width}x{self._raw_height}) is bigger than source frame size ({frame_w}x{frame_h})."
                              f" Setting RAW size to frame size.")
                self._raw_width = frame_w
                self._raw_height = frame_h
            if self._video_width > frame_w or self._video_height > frame_h:
                logging.error(f"VIDEO frame size ({self._video_width}x{self._video_height}) is bigger than source frame size ({frame_w}x{frame_h})."
                              f" Setting VIDEO size to frame size.")
                self._video_width = frame_w
                self._video_height = frame_h

            timestamp: timedelta = timedelta(seconds=time.time() - send_video_frames_start)

            # NOTE(miha): Mock input control commands
            if self._input_control_queue is not None:
                if self._input_control_queue.has():
                    ctrl: dai.CameraControl = self._input_control_queue.get()  # type: ignore
                    if ctrl.getCaptureStill():
                        self._send_capture_still = True
            if self._input_config_queue is not None:
                pass

            if self._raw_queue is not None:
                raw_img_frame = create_img_frame(
                    data=to_planar(frame, (self._raw_width, self._raw_height)),
                    width=self._raw_width,
                    height=self._raw_height,
                    type=dai.ImgFrame.Type.BGR888p,
                    sequence_number=sequence_number,
                    timestamp=timestamp,
                    camera_socket=self._camera_socket,
                )
                self._raw_queue.send(raw_img_frame)
            if self._use_nv12_frame:
                isp_frame = cv2.resize(frame, (self._isp_width, self._isp_height))
                isp_nv12_frame = BGR2YUV_NV12(isp_frame)
                video_nv12_frame = None
                if self._isp_queue is not None:
                    isp_img_frame = create_img_frame(
                        data=isp_nv12_frame,
                        width=self._isp_width,
                        height=self._isp_height,
                        type=dai.ImgFrame.Type.NV12,
                        sequence_number=sequence_number,
                        timestamp=timestamp,
                        camera_socket=self._camera_socket,
                    )
                    self._isp_queue.send(isp_img_frame)
                if self._video_queue is not None:
                    if self._video_width == self._isp_width and self._video_height == self._isp_height:
                        video_nv12_frame = isp_nv12_frame
                    else:
                        video_frame = cv2.resize(frame, (self._video_width, self._video_height))
                        video_nv12_frame = BGR2YUV_NV12(video_frame)
                    video_img_frame = create_img_frame(
                        data=video_nv12_frame,
                        width=self._video_width,
                        height=self._video_height,
                        type=dai.ImgFrame.Type.NV12,
                        sequence_number=sequence_number,
                        timestamp=timestamp,
                        camera_socket=self._camera_socket,
                    )
                    self._video_queue.send(video_img_frame)
                if self._still_queue is not None and self._send_capture_still:
                    if self._still_width == self._isp_width and self._still_height == self._isp_height:
                        still_nv12_frame = isp_nv12_frame
                    elif video_nv12_frame is not None and self._still_width == self._video_width and self._still_height == self._video_width:
                        still_nv12_frame = video_nv12_frame
                    else:
                        still_frame = cv2.resize(frame, (self._still_width, self._still_height))
                        still_nv12_frame = BGR2YUV_NV12(still_frame)
                    self._send_capture_still = False
                    video_img_frame = create_img_frame(
                        data=still_nv12_frame,
                        width=self._video_width,
                        height=self._video_height,
                        type=dai.ImgFrame.Type.NV12,
                        sequence_number=sequence_number,
                        timestamp=timestamp,
                        camera_socket=self._camera_socket,
                    )
                    self._still_queue.send(video_img_frame)

            if self._preview_queue is not None:
                preview_frame = frame
                # crop when preview aspect ratio is different to video aspect ratio
                if self._preview_crop_needed is None:
                    self._find_if_preview_crop_needed()
                if self._preview_crop_needed:
                    if self._preview_x_coords is None:
                        self._find_preview_crop_coords()
                    preview_frame = frame[:, self._preview_x_coords[0]:self._preview_x_coords[1], :]

                preview_frame = cv2.resize(preview_frame, (self._preview_width, self._preview_height))
                preview_img_frame = create_img_frame(
                    data=to_planar(preview_frame, (self._preview_width, self._preview_height)),
                    width=self._preview_width,
                    height=self._preview_height,
                    type=dai.ImgFrame.Type.BGR888p,
                    sequence_number=sequence_number,
                    timestamp=timestamp,
                    camera_socket=self._camera_socket,
                )
                if self._preview_queue is not None:
                    self._preview_queue.send(preview_img_frame)

            sequence_number += 1

            process_time = time.monotonic() - start
            if process_time > 1.0 / self._fps:
                logging.error(
                    f"Proccessing time ({process_time:.3f}ms) didn't hit the set camera FPS deadline ({1. / self._fps:.3f}ms)"
                )
            time_to_sleep = max((1.0 / self._fps) - process_time, 0)
            logging.debug(f"process_time: {process_time}, time_to_sleep: {time_to_sleep}")
            time.sleep(time_to_sleep)

        self._capture_manager.close()

    def start_polling(self, device: dai.Device):
        self._thread = threading.Thread(target=self._send_video_frames, args=(device,))
        self._thread.start()

    def stop_polling(self):
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join()

    @property
    def replay_is_running(self) -> bool:
        return not self._stop_event.is_set()

    def _find_if_preview_crop_needed(self):
        self._preview_crop_needed = abs(self._video_width / self._video_height - self._preview_width / self._preview_height) > 0.1

    def _find_preview_crop_coords(self):
        new_width = self._video_height * self._preview_width // self._preview_height
        x_middle = self._video_width // 2 + self._video_width % 2
        self._preview_x_coords = (x_middle - new_width // 2, x_middle + new_width // 2 + new_width % 2)

    # NOTE(miha): Below are methods for ColorCamera class:

    def getBoardSocket(self) -> dai.CameraBoardSocket | None:
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
        if width > self._video_width or height > self._video_height:
            raise ValueError(f"Preview size ({width}x{height}) is larger than video size ({self._video_width}x{self._video_height})")
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
        self._nodes[self._stream_name.VIDEO].setMaxDataSize(width * height * 3 // 2)

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


class MonoReplayCamera(ReplayCamera):
    def __init__(
            self,
            pipeline: dai.Pipeline,
            fps: float,
            src: str | List[str],
            run_in_loop: bool = True,
            start: Optional[int] = None,
            end: Optional[int] = None,
    ):
        super().__init__()
        self.replay_camera_instances.append(self)
        self._stream_name: StreamName = StreamName(suffix=str(len(self.replay_camera_instances)))

        self._input_control: Optional[dai.Node.Input] = None
        self._raw: Optional[dai.Node.Output] = None
        self._out: Optional[dai.Node.Output] = None

        self._input_control_queue: Optional[dai.DataOutputQueue] = None
        self._raw_queue: Optional[dai.DataInputQueue] = None
        self._out_queue: Optional[dai.DataInputQueue] = None

        self._fps: float = fps
        self._start = start
        self._end = start
        self._run_in_loop = run_in_loop
        self._pipeline: dai.Pipeline = pipeline

        self._raw_width: int = 1920
        self._raw_height: int = 1080
        self._out_width: int = 1280
        self._out_height: int = 800
        self._color_order: dai.ColorCameraProperties.ColorOrder = dai.ColorCameraProperties.ColorOrder.BGR
        self._interleaved = False
        self._camera_socket: dai.CameraBoardSocket | None = None

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        if isinstance(src, str):
            src = [src]

        self._capture_manager = CaptureManager(src, self._run_in_loop, self._start, self._end)

        # NOTE(miha): Used for saving references to nodes if we want to set max
        # data size later (i.e. calling setPreviewSize also alter max data size).
        self._nodes = {}

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

        if self._raw is not None:
            self._raw_queue = device.getInputQueue(name=self._stream_name.RAW)
        if self._out is not None:
            self._out_queue = device.getInputQueue(name=self._stream_name.GRAY)

        sequence_number = 0
        send_video_frames_start = time.time()

        while rh.app_is_running() and self.replay_is_running:
            start = time.monotonic()

            # NOTE(miha): Returned frame is in BGR format
            frame = self._capture_manager.get_next_frame()
            if frame is None:
                break

            timestamp: timedelta = timedelta(seconds=time.time() - send_video_frames_start)

            # NOTE(miha): Mock input control commands

            if self._raw_queue is not None:
                raw_img_frame = create_img_frame(
                    data=to_planar(frame, (self._raw_width, self._raw_height)),
                    width=self._raw_width,
                    height=self._raw_height,
                    type=dai.ImgFrame.Type.BGR888p,
                    sequence_number=sequence_number,
                    timestamp=timestamp,
                    camera_socket=self._camera_socket,
                )
                self._raw_queue.send(raw_img_frame)

            if self._out_queue is not None:
                preview_frame = cv2.resize(frame, (self._out_width, self._out_height))
                preview_img_frame = create_img_frame(
                    data=to_planar(preview_frame, (self._out_width, self._out_height)),
                    width=self._out_width,
                    height=self._out_height,
                    type=dai.ImgFrame.Type.BGR888p,
                    sequence_number=sequence_number,
                    timestamp=timestamp,
                    camera_socket=self._camera_socket,
                )
                self._out_queue.send(preview_img_frame)

            sequence_number += 1

            process_time = time.monotonic() - start
            if process_time > 1.0 / self._fps:
                logging.error(
                    f"Proccessing time ({process_time:.3f}ms) didn't hit the set camera FPS deadline ({1. / self._fps:.3f}ms)"
                )
            time_to_sleep = max((1.0 / self._fps) - process_time, 0)
            logging.debug(f"process_time: {process_time}, time_to_sleep: {time_to_sleep}")
            time.sleep(time_to_sleep)

        self._capture_manager.close()

    def start_polling(self, device: dai.Device):
        thread = threading.Thread(target=self._send_video_frames, args=(device,))
        thread.start()

    def stop_polling(self):
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join()

    @property
    def replay_is_running(self) -> bool:
        return not self._stop_event.is_set()

    def getBoardSocket(self) -> dai.CameraBoardSocket | None:
        return self._camera_socket

    def getCamId(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def getCamera(self) -> str:
        raise NotImplementedError("This function is not yet implemented")

    def getFps(self) -> float:
        raise NotImplementedError("This function is not yet implemented")

    def getFrameEventFilter(self) -> List[dai.FrameEvent]:
        raise NotImplementedError("This function is not yet implemented")

    def getImageOrientation(self) -> dai.CameraImageOrientation:
        raise NotImplementedError("This function is not yet implemented")

    def getNumFramesPool(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def getRawNumFramesPool(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def getResolution(self) -> dai.MonoCameraProperties.SensorResolution:
        raise NotImplementedError("This function is not yet implemented")

    def getResolutionHeight(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def getResolutionSize(self) -> Tuple[int, int]:
        raise NotImplementedError("This function is not yet implemented")

    def getResolutionWidth(self) -> int:
        raise NotImplementedError("This function is not yet implemented")

    def setBoardSocket(self, boardSocket: dai.CameraBoardSocket) -> None:
        self._camera_socket = boardSocket

    def setCamId(self, arg0: int) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setCamera(self, name: str) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setFps(self, fps: float) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setFrameEventFilter(self, events: List[dai.FrameEvent]) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setImageOrientation(self, imageOrientation: dai.CameraImageOrientation) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setIsp3aFps(self, arg0: int) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setNumFramesPool(self, arg0: int) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setRawNumFramesPool(self, arg0: int) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setRawOutputPacked(self, packed: bool) -> None:
        raise NotImplementedError("This function is not yet implemented")

    def setResolution(self, resolution: dai.MonoCameraProperties.SensorResolution) -> None:
        raise NotImplementedError("This function is not yet implemented")

    @property
    def frameEvent(self) -> dai.Node.Output:
        raise NotImplementedError("This function is not yet implemented")

    @property
    def initialControl(self) -> dai.CameraControl:
        raise NotImplementedError("This function is not yet implemented")

    @property
    def inputControl(self) -> dai.Node.Input:
        if self._input_control is None:
            self._input_control = self._create_cam_input(self._pipeline, self._stream_name.INPUT_CONTROL)
        return self._input_control

    @property
    def out(self) -> dai.Node.Output:
        if self._out is None:
            node_out = self._create_cam_output(self._pipeline, self._stream_name.GRAY)
            manip = self._pipeline.createImageManip()
            manip.setFrameType(dai.RawImgFrame.Type.RAW8)
            manip.setResize(self._out_width, self._out_height)
            manip.setKeepAspectRatio(False)
            node_out.link(manip.inputImage)
            self._out = manip.out
        return self._out

    @property
    def raw(self) -> dai.Node.Output:
        if self._raw is None:
            self._raw = self._create_cam_output(self._pipeline, self._stream_name.RAW)
        return self._raw
