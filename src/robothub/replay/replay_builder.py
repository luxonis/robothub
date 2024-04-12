import glob
import logging
from enum import Enum, auto
from typing import List, Optional

import depthai as dai
from robothub.replay.replay_camera import ColorReplayCamera, MonoReplayCamera

__all__ = ["ReplayBuilder"]


class CameraType(Enum):
    COLOR = auto()
    MONO = auto()


class ReplayBuilder:
    def __init__(self, pipeline: dai.Pipeline, fps: Optional[float]):
        self._pipeline: dai.Pipeline = pipeline

        if fps is not None:
            self._fps: float = fps

        self._media_src: List[str] = []
        self._camera_type: Optional[CameraType] = None
        self._start: Optional[int] = None
        self._end: Optional[int] = None
        self._run_in_loop = True

    def frames_range(self, start: Optional[int] = None, end: Optional[int] = None):
        if start is not None:
            self._start = start
        if end is not None:
            self._end = end
        return self

    def files(self, src: str):
        files = glob.glob(src)
        self._media_src.extend(files)
        return self

    def recursive_files(self, src: str):
        files = glob.glob(src, recursive=True)
        self._media_src.extend(files)
        return self

    def hidden_files(self, src: str):
        files = glob.glob(src, include_hidden=True)
        self._media_src.extend(files)
        return self

    def youtube_video(self, tmp_dir=None):
        # TODO(miha): Download yt video, save it in tmp dir, add it to self._media_src
        raise NotImplementedError("Youtube videos not implemented yet")

    def sort_files(self):
        self._media_src.sort()
        return self

    def log_info(self):
        logging.info(f"Using following source files: {self._media_src}")
        logging.info(
            f"Replay camera configuration: fps: {self._fps}, run_in_loop: {self._run_in_loop}, start: {self._start}, end: {self._end}"
        )
        return self

    def build_color_camera(self) -> ColorReplayCamera:
        if self._fps is None:
            logging.warning("Setting FPS to its default value 5")
            self._fps = 5.0
        return ColorReplayCamera(
            pipeline=self._pipeline,
            src=self._media_src,
            fps=self._fps,
            run_in_loop=self._run_in_loop,
            start=self._start,
            end=self._end,
        )

    def build_mono_camera(self) -> MonoReplayCamera:
        if self._fps is None:
            logging.warning("Setting FPS to its default value 5")
            self._fps = 5.0
        return MonoReplayCamera(
            pipeline=self._pipeline,
            src=self._media_src,
            fps=self._fps,
            run_in_loop=self._run_in_loop,
            start=self._start,
            end=self._end,
        )

    # def new_color_camera(self) -> Self:
    #     self._camera_type = CameraType.COLOR
    #     return self
    #
    # def new_mono_camera(self) -> Self:
    #     self._camera_type = CameraType.MONO
    #     return self
    #
    # def build(self) -> ReplayCamera:
    #     if self._camera_type is None:
    #         raise ValueError("camera type can't be None")
    #
    #     if self._camera_type == CameraType.COLOR:
    #         return ColorReplayCamera(
    #             pipeline=self._pipeline,
    #             src=self._media_src,
    #             fps=self._fps,
    #             run_in_loop=self._run_in_loop,
    #             start=self._start,
    #             end=self._end,
    #         )
    #     elif self._camera_type == CameraType.MONO:
    #         return MonoReplayCamera(
    #             pipeline=self._pipeline,
    #             src=self._media_src,
    #             fps=self._fps,
    #             run_in_loop=self._run_in_loop,
    #             start=self._start,
    #             end=self._end,
    #         )
    #
    #     raise ValueError("camera type can't be None")
