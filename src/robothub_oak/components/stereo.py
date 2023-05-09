from enum import IntEnum
from typing import Union, Optional

from robothub_oak.components.streamable import Streamable

__all__ = ['Stereo', 'DepthQuality', 'DepthRange']


class DepthQuality(IntEnum):
    FAST = 1  # nothing turned on
    DEFAULT = 2  # lr check, median filter
    QUALITY = 3  # lr check, subpixel


class DepthRange(IntEnum):
    SHORT = 1  # extended disparity
    DEFAULT = 2  # no effect
    LONG = 3  # subpixel


class Stereo(Streamable):
    def __init__(self,
                 resolution: Optional[str],
                 fps: Optional[int],
                 left_camera: Optional['Camera'] = None,
                 right_camera: Optional['Camera'] = None):
        """
        This component represents the stereo module of the OAK device.

        :param resolution: Resolution of the disparity/depth map. Can be one of '400p', '480p', '720p', or '800p'.
        :param fps: FPS of the stereo output.
        :param left_camera: Left camera component.
        :param right_camera: Right camera component.
        """
        super().__init__()
        self.resolution = resolution
        self.fps = fps

        self.left_camera = left_camera
        self.right_camera = right_camera

        self.quality = DepthQuality.DEFAULT
        self.range = DepthRange.DEFAULT

        self.align = 'color'
        self.stereo_component = None  # type: depthai_sdk.components.StereoComponent

    def configure(self,
                  depth_quality: Union[str, DepthQuality] = None,
                  depth_range: Union[str, DepthRange] = None,
                  align: str = None) -> None:
        """
        Configures the stereo component.

        :param depth_quality: Quality of the depth map. Can be one of 'fast', 'default' or 'quality'.
        :param depth_range: Working range of the stereo module. Can be one of 'short', 'default' or 'long'.
        :param align: Alignment of the depth map. Can be one of 'color', 'left', 'right' or 'cama,c' (or similar). Defaults to 'color'.
        """
        if depth_quality:
            self.quality = self._set_enum_value(DepthQuality, depth_quality)
        if depth_range:
            self.range = self._set_enum_value(DepthRange, depth_range)
        if align:
            self.align = align

    @staticmethod
    def _set_enum_value(enum, value):
        if isinstance(value, str):
            return enum[value.upper()]
        elif isinstance(value, enum):
            return value
        else:
            raise ValueError(f'Invalid value: {value}')
