import pathlib
from enum import Enum, auto
from typing import List, Optional, Tuple

import numpy as np

from robothub.replay.captures import (Capture, ImageDirectoryCapture,
                                      VideoCapture)


class PathType(Enum):
    VIDEO = auto()
    IMAGE_DIRECTORY = auto()
    IMAGE = auto()


class ReadFrameType(Enum):
    NORMAL = auto()
    NEXT = auto()
    PREV = auto()
    JUMP = auto()


VideoSuffixes = [".mp4", ".avi"]
ImageSuffixes = [".jpg", ".jpeg", ".png"]


class CaptureManager:
    def __init__(
        self,
        src: List[str],
        run_in_loop=True,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ):
        self._run_in_loop = run_in_loop

        self._start = 0
        if start is not None:
            self._start = start

        self._end = None
        if end is not None:
            self._end = end

        self._frame_index = 0 if start is None else start
        self._capture_index = 0

        self._pause = False

        self._path_type: Optional[PathType] = None
        self._read_frame_type: ReadFrameType = ReadFrameType.NORMAL

        self._parse_src(src)
        if self._path_type is None:
            raise ValueError("Error in parsing source")
        self._create_capture()

    def _parse_src(self, src: List[str]):
        self._paths = [pathlib.Path(s).resolve() for s in src]

        suffixes: List[PathType] = []
        for path in self._paths:
            if path.suffix in VideoSuffixes:
                suffixes.append(PathType.VIDEO)
            elif path.suffix in ImageSuffixes:
                suffixes.append(PathType.IMAGE)
            elif path.suffix == "":
                suffixes.append(PathType.IMAGE_DIRECTORY)
            else:
                raise ValueError(f"File {str(path)} is of unknown format, capture can't work with it.")

        if all([s == PathType.VIDEO for s in suffixes]):
            self._path_type = PathType.VIDEO
        elif all([s == PathType.IMAGE for s in suffixes]):
            self._path_type = PathType.IMAGE
        elif all([s == PathType.IMAGE_DIRECTORY for s in suffixes]):
            self._path_type = PathType.IMAGE_DIRECTORY
        else:
            raise ValueError(f"Listed files: {src}, can only be one of the following: images, videos, directories.")

    def set_start(self, value: int):
        self._start = value

    def set_end(self, value: int):
        self._end = value

    def _create_capture(self):
        if self._path_type == PathType.VIDEO:
            self._capture = VideoCapture(self._paths[self._capture_index])
        elif self._path_type == PathType.IMAGE:
            # self._capture = ImageCapture(self._paths[self._capture_index])
            pass
        elif self._path_type == PathType.IMAGE_DIRECTORY:
            self._capture = ImageDirectoryCapture(self._paths[self._capture_index])
        else:
            raise NotImplementedError(f"Unknown type: {self._path_type}")
        self._capture.reset(self._start)
        self._frame_index = self._start

    @property
    def _should_move_to_next_capture(self) -> bool:
        if not self._run_in_loop and self._capture_index + 1 >= len(self._paths):
            return False
        return True

    def _move_to_next_capture(self):
        if len(self._paths) > 1:
            self._capture.close()
            self._capture_index += 1
            self._capture_index %= len(self._paths)
            self._create_capture()

    def _reset_capture(self):
        self._move_to_next_capture()
        self._capture.reset(self._start)
        self._frame_index = self._start

    def get_capture(self) -> Capture:
        return self._capture

    def next_frame(self):
        self._read_frame_type = ReadFrameType.NEXT

    def prev_frame(self):
        self._read_frame_type = ReadFrameType.PREV

    def jump_to_frame(self, index):
        self._read_frame_type = ReadFrameType.JUMP
        self._jump_index = index

    def toggle_pause(self):
        self._pause = not self._pause

    # NOTE(miha): With more complex logic for getting frame (i.e. next, prev frame), we
    # need a function to handle such exotic cases.
    # TODO(miha): We don't handle cases where next_frame should go to the next capture, ...
    def _read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        next_frame_exists = False
        frame = None

        if self._read_frame_type == ReadFrameType.NORMAL:
            if self._pause:
                next_frame_exists, frame = self._capture.read(self._frame_index)
            else:
                next_frame_exists, frame = self._capture.read()
        elif self._read_frame_type == ReadFrameType.NEXT:
            self._frame_index += 1
            next_frame_exists, frame = self._capture.read(self._frame_index)
            self._read_frame_type = ReadFrameType.NORMAL
        elif self._read_frame_type == ReadFrameType.PREV:
            self._frame_index -= 1
            next_frame_exists, frame = self._capture.read(self._frame_index)
            self._read_frame_type = ReadFrameType.NORMAL
        elif self._read_frame_type == ReadFrameType.JUMP:
            self._frame_index = self._jump_index
            next_frame_exists, frame = self._capture.read(self._frame_index)
            self._read_frame_type = ReadFrameType.NORMAL

        return next_frame_exists, frame

    def get_next_frame(self) -> Optional[np.ndarray]:
        if not self._capture.is_opened():
            return None

        if self._end is not None and self._frame_index > self._end:
            self._reset_capture()

        if self._frame_index < self._start:
            self._reset_capture()

        frame = None
        for _ in range(2):
            # next_frame_exists, frame = self._capture.read()
            next_frame_exists, frame = self._read_frame()

            if not next_frame_exists and self._should_move_to_next_capture:
                self._reset_capture()
                continue
            break

        if not self._pause:
            self._frame_index += 1
        return frame

    def close(self):
        self._capture.close()
