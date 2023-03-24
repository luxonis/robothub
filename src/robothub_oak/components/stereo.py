from enum import IntEnum
from typing import Union

from robothub_oak.components.streamable import Streamable

__all__ = ['Stereo']


class DepthQuality(IntEnum):
    FAST = 1  # nothing turned on
    DEFAULT = 2  # lr check, median filter
    QUALITY = 3  # lr check, subpixel


class DepthRange(IntEnum):
    SHORT = 1  # extended disparity
    DEFAULT = 2  # no effect
    LONG = 3  # subpixel


class Stereo(Streamable):
    def __init__(self, resolution: str, fps: int, left_camera: 'Camera' = None, right_camera: 'Camera' = None) -> None:
        super().__init__()
        self.resolution = resolution
        self.fps = fps

        self.left_camera = left_camera
        self.right_camera = right_camera

        self.quality = DepthQuality.DEFAULT
        self.range = DepthRange.DEFAULT

        self.stereo_component = None  # type: depthai_sdk.components.StereoComponent

    def configure(self, quality: Union[str, DepthQuality] = None, range: Union[str, DepthRange] = None) -> None:
        if quality:
            self.quality = self._set_enum_value(DepthQuality, quality)
        if range:
            self.range = self._set_enum_value(DepthRange, range)

    @staticmethod
    def _set_enum_value(enum, value):
        if isinstance(value, str):
            return enum[value.upper()]
        elif isinstance(value, enum):
            return value
        else:
            raise ValueError(f'Invalid value: {value}')
