import logging
import os
import pathlib
import threading
import time
from datetime import timedelta
from enum import Enum, auto
from typing import List, Optional, Tuple

import cv2
import depthai as dai
import numpy as np

# TODO(miha):
#   - pause toggle (when paused we don't read video)
#   - should we use img_manip node to resize preview or cv2?
#   - get actual sizes for raw, isp
#   - test loop=False


class PathType(Enum):
    VIDEO = auto()
    IMAGE_DIRECTORY = auto()


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
    def __init__(self, pipeline: dai.Pipeline, fps: float, src: str, loop: bool = True):
        # NOTE(miha): Replay node inputs/outputs
        self._input_control: dai.Node.Input
        self._input_config: dai.Node.Input
        self._raw: dai.Node.Output
        self._isp: dai.Node.Output
        self._video: dai.Node.Output
        self._still: dai.Node.Output
        self._preview: dai.Node.Output
        # self.frameEvent: dai.Node.Output
        # self.InitialControl: dai.CameraControl

        self._fps: float = fps
        self._video_width: int = 1920
        self._video_height: int = 1080
        self._preview_width: int = 1280
        self._preview_height: int = 720
        self._color_order: dai.ColorCameraProperties.ColorOrder = dai.ColorCameraProperties.ColorOrder.BGR
        self._interleaved = False
        self._loop = loop

        self._path_type: PathType
        self._path = self._parse_src(src)
        if self._path is None:
            logging.error(f"Error in parsing src: {src}")
            return

        self.INPUT_CONTROL_STREAM_NAME = "input_control"
        self.INPUT_CONFIG_STREAM_NAME = "input_config"
        self.RAW_STREAM_NAME = "raw"
        self.ISP_STREAM_NAME = "isp"
        self.VIDEO_STREAM_NAME = "video"
        self.STILL_STREAM_NAME = "still"
        self.PREVIEW_STREAM_NAME = "preview"

        # NOTE(miha): Used for saving references to nodes if we want to set max
        # data size later (i.e. calling setPreviewSize also alter max data size).
        self._nodes = {}

        self._input_control = self._create_cam_input(pipeline, self.INPUT_CONTROL_STREAM_NAME)
        self._input_config = self._create_cam_input(pipeline, self.INPUT_CONFIG_STREAM_NAME)
        self._raw = self._create_cam_output(pipeline, self.RAW_STREAM_NAME)
        self._isp = self._create_cam_output(pipeline, self.ISP_STREAM_NAME)
        self._video = self._create_cam_output(
            pipeline, self.VIDEO_STREAM_NAME, self._video_width * self._video_height * 3
        )
        self._still = self._create_cam_output(pipeline, self.STILL_STREAM_NAME)
        self._preview = self._create_cam_output(
            pipeline,
            self.PREVIEW_STREAM_NAME,
            self._preview_width * self._preview_height * 3,
        )
        # self.img_manip = pipeline.create(dai.node.ImageManip)
        # self.img_manip.initialConfig.setResizeThumbnail(self.preview_width, self.preview_height)
        # self.img_manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888p)
        # self.preview = self.img_manip.out

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

    def send_video_frames(self, device: dai.Device):
        self._input_control_queue = device.getOutputQueue(name=self.INPUT_CONTROL_STREAM_NAME)
        self._input_config_queue = device.getOutputQueue(name=self.INPUT_CONFIG_STREAM_NAME)

        self._raw_queue = device.getInputQueue(name=self.RAW_STREAM_NAME)
        self._isp_queue = device.getInputQueue(name=self.ISP_STREAM_NAME)
        self._video_queue = device.getInputQueue(name=self.VIDEO_STREAM_NAME)
        self._still_queue = device.getInputQueue(name=self.STILL_STREAM_NAME)
        self._preview_queue = device.getInputQueue(name=self.PREVIEW_STREAM_NAME)

        if self._path_type == PathType.VIDEO:
            self._cap = cv2.VideoCapture(str(self._path))
        else:
            self._cap = ImageDirectoryCapture(self._path)  # type: ignore

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
            return img_frame

        def get_next_frame():
            if not self._cap.isOpened():
                return None

            frame = None
            for _ in range(2):
                ok, frame = self._cap.read()
                if not ok and self._loop:
                    self._cap.release()
                    if self._path_type == PathType.VIDEO:
                        self._cap = cv2.VideoCapture(str(self._path))
                    else:
                        self._cap.reset()  # type:ignore
                    continue
                break

            return frame

        while True:
            start = time.monotonic()

            # NOTE(miha): Returned frame is in BGR format
            frame = get_next_frame()
            if frame is None:
                break

            nv12_frame = BGR2YUV_NV12(frame)
            preview_frame = cv2.resize(frame, (self._preview_width, self._preview_height))

            timestamp: timedelta = timedelta(seconds=time.time() - send_video_frames_start)

            video_img_frame = create_img_frame(
                data=nv12_frame,
                width=self._video_width,
                height=self._video_height,
                type=dai.ImgFrame.Type.NV12,
                sequence_number=sequence_number,
                timestamp=timestamp,
            )
            preview_img_frame = create_img_frame(
                data=to_planar(preview_frame, (self._preview_width, self._preview_height)),
                width=self._preview_width,
                height=self._preview_height,
                type=dai.ImgFrame.Type.BGR888p,
                sequence_number=sequence_number,
                timestamp=timestamp,
            )

            sequence_number += 1

            # TODO(miha): Send to other queues as well
            self._video_queue.send(video_img_frame)
            self._preview_queue.send(preview_img_frame)

            # NOTE(miha): Mock input control commands
            if self._input_control_queue.has():
                ctrl: dai.CameraControl = self._input_control_queue.get()  # type: ignore

                # TODO(miha): Send image to still queue
                if ctrl.getCaptureStill():
                    pass

            process_time = time.monotonic() - start
            if process_time > (1000.0 / self._fps) / 1000.0:
                logging.error(
                    f"Proccessing time ({process_time}) didn't hit the set camera FPS deadline ({1000.0 / self._fps})"
                )
            time_to_sleep = max((1000.0 / self._fps / 1000.0) - process_time, 0)
            logging.debug(f"process_time: {process_time}, time_to_sleep: {time_to_sleep}")
            time.sleep(time_to_sleep)

        time.sleep(self._fps)  # NOTE(miha): Wait for last message to arrive
        self._cap.release()
        cv2.destroyAllWindows()

    def start_pooling(self, device: dai.Device):
        self.thread = threading.Thread(target=self.send_video_frames, args=(device,))
        self.thread.start()

    def stop_pooling(self):
        self.thread.join()

    # NOTE(miha): Below are methods for ColorCamera class:

    def getBoardSocket(self) -> dai.CameraBoardSocket:
        raise NotImplementedError("This function is not yet implemented")

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
        raise NotImplementedError("This function is not yet implemented")

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
        self._preview_width = width
        self._preview_height = height
        self._nodes[self.PREVIEW_STREAM_NAME].setMaxDataSize(width * height * 3)

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
        self._video_width = width
        self._video_height = height

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
        return self._input_control

    @property
    def inputControl(self) -> dai.Node.Input:
        return self._input_control

    @property
    def isp(self) -> dai.Node.Output:
        return self._isp

    @property
    def preview(self) -> dai.Node.Output:
        return self._preview

    @property
    def raw(self) -> dai.Node.Output:
        return self._raw

    @property
    def still(self) -> dai.Node.Output:
        return self._still

    @property
    def video(self) -> dai.Node.Output:
        return self._video
