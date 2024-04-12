import logging
import os
import pathlib
from abc import ABC, abstractmethod
from typing import Optional, Tuple

import cv2
import numpy as np


class Capture(ABC):

    @abstractmethod
    def read(self, index: Optional[int] = None) -> Tuple[bool, Optional[np.ndarray]]:
        pass

    @abstractmethod
    def reset(self, seek: Optional[int]):
        pass

    @abstractmethod
    def is_opened(self) -> bool:
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def length(self) -> int:
        pass


class ImageDirectoryCapture(Capture):
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

    def read(self, index: int | None = None) -> Tuple[bool, Optional[np.ndarray]]:
        image_index = index if index is not None else self.current_frame

        frame = None
        if image_index < len(self.image_files):
            frame = cv2.imread(self.image_files[image_index])

        # NOTE(miha): self.current_frame index was used
        if index is None:
            self.current_frame += 1

        return frame is not None, frame

    def reset(self, seek: Optional[int] = None):
        self.current_frame = 0 if seek is None else seek

    def is_opened(self) -> bool:
        return True

    def close(self):
        pass

    def length(self) -> int:
        return len(self.image_files)


# class PyAvVideoCapture(Capture):
#     def __init__(self, path: pathlib.Path):
#         self.container = av.open(str(path))
#         self.video = self.container.streams.video[0]
#
#     def _next_frame(self):
#         for frame in self.container.decode(video=0):
#             yield True, frame.to_rgb().to_ndarray()
#
#     @overload
#     def read(self, index: None = None) -> Tuple[bool, Optional[np.ndarray]]:
#         pass
#
#     @overload
#     def read(self, index: int) -> Tuple[bool, Optional[np.ndarray]]:
#         pass
#
#     def read(self, index: int | None = None) -> Tuple[bool, Optional[np.ndarray]]:
#         if index is not None:
#             raise NotImplementedError("Reading at index is not supported for PyAvVideoCapture")
#
#         try:
#             has_next_frame, frame = next(self._next_frame())
#             # NOTE(miha): Convert RGB to BGR
#             return has_next_frame, frame[:, :, ::-1]
#         except av.error.EOFError:  # type: ignore
#             return False, None
#
#     def reset(self, seek: Optional[int] = None):
#         # CARE(miha): Seek doesn't work, we always go to the start of the video.
#         self.container.seek(0)
#
#     def is_opened(self) -> bool:
#         return self.container is not None
#
#     def close(self):
#         self.container.close()
#
#     def length(self) -> int:
#         return 0


class VideoCapture(Capture):
    def __init__(self, path: pathlib.Path):
        self.capture = cv2.VideoCapture(str(path))

    def read(self, index: int | None = None) -> Tuple[bool, Optional[np.ndarray]]:
        if index is not None:
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        return self.capture.read()

    def reset(self, seek: Optional[int] = None):
        num_frames = self.capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if seek is not None and seek > num_frames:
            logging.warning(f"Video has {num_frames} frames, can't start it at frame: {seek}")
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0 if seek is None else seek)

    def is_opened(self) -> bool:
        return self.capture.isOpened()

    def close(self):
        self.capture.release()

    def length(self) -> int:
        num_frames = self.capture.get(cv2.CAP_PROP_FRAME_COUNT)
        return int(num_frames)
