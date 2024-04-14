import glob
import logging as log
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional

import depthai as dai
from robothub.replay.replay_camera import ColorReplayCamera, MonoReplayCamera

__all__ = ["ReplayBuilder"]


class CameraType(Enum):
    COLOR = auto()
    MONO = auto()


class ReplayBuilder:
    def __init__(self, pipeline: dai.Pipeline, fps: float = 5):
        self._pipeline: dai.Pipeline = pipeline

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
        log.info(f"Using following source files: {self._media_src}")
        log.info(
            f"Replay camera configuration: fps: {self._fps}, run_in_loop: {self._run_in_loop}, start: {self._start}, end: {self._end}"
        )
        return self

    def change_mp4_video_frame_rate(self, new_fps: float):
        """
        Replay FPS is usually capped between 5 - 15 FPS depending on Replay configuration.
        When the source .mp4 file(s) are at much higher FPS then that, this allows to convert them to lower FPS.
        Videos are converted and stored at the same location as the source video.
        """
        try:
            import ffmpeg
        except ImportError:
            raise ImportError("Please install ffmpeg to use this feature.\nRun 'pip install ffmpeg-python'\nCareful DON'T run 'pip install ffmpeg'"
                              " its a different library and it will not work here.")
        new_media = []
        for media in self._media_src:
            media_already_converted = False
            media_path = Path(media)
            media_parent = media_path.parent
            files_in_parent = list(media_parent.glob("*.mp4"))

            input_file = media
            output_file = input_file.replace(".mp4", f"_{new_fps}fps.mp4")
            new_media.append(output_file)
            for file in files_in_parent:
                if output_file in file.as_posix():
                    media_already_converted = True
                    break
            if media_already_converted:
                continue
            log.warning(f"Converting {media} to {new_fps} fps")
            (ffmpeg.input(input_file)
             .output(output_file, r=new_fps)
             .run(overwrite_output=True))  # Overwrite the output file if it exists
        self._media_src = new_media
        return self

    def build_color_camera(self) -> ColorReplayCamera:
        if self._fps is None:
            log.warning("Setting FPS to its default value 5")
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
            log.warning("Setting FPS to its default value 5")
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
