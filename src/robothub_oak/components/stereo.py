from dataclasses import dataclass, replace
from enum import IntEnum
from typing import Union, Optional

import depthai as dai

from robothub_oak.components._streamable import Streamable
from robothub_oak.utils import _process_kwargs

__all__ = ['Stereo', 'DepthQuality', 'DepthRange']


class DepthQuality(IntEnum):
    FAST = 1  # nothing turned on
    DEFAULT = 2  # lr check, median filter
    QUALITY = 3  # lr check, subpixel


class DepthRange(IntEnum):
    SHORT = 1  # extended disparity
    DEFAULT = 2  # no effect
    LONG = 3  # subpixel


@dataclass
class StereoConfig:
    """
    Dataclass representing the configuration of the stereo component.
    """
    depth_quality: Union[str, DepthQuality] = None
    depth_range: Union[str, DepthRange] = None
    align: Optional['Camera'] = None
    confidence: Optional[int] = None
    median: Union[None, int, dai.MedianFilter] = None
    extended: Optional[bool] = None
    subpixel: Optional[bool] = None
    lr_check: Optional[bool] = None
    sigma: Optional[int] = None
    lr_check_threshold: Optional[int] = None


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

        self.stereo_config = StereoConfig()
        self.stereo_component = None  # type: depthai_sdk.components.StereoComponent

    def configure(self,
                  depth_quality: Union[str, DepthQuality] = None,
                  depth_range: Union[str, DepthRange] = None,
                  align: 'Camera' = None,
                  confidence: Optional[int] = None,
                  median: Union[None, int, dai.MedianFilter] = None,
                  extended: Optional[bool] = None,
                  subpixel: Optional[bool] = None,
                  lr_check: Optional[bool] = None,
                  sigma: Optional[int] = None,
                  lr_check_threshold: Optional[int] = None,
                  ) -> None:
        """
        Configures the stereo component.

        :param depth_quality: Quality of the depth map. Can be one of 'fast', 'default' or 'quality'.
        :param depth_range: Working range of the stereo module. Can be one of 'short', 'default' or 'long'.
        :param align: Alignment of the depth map. Can be a camera component.
        :param confidence: Confidence threshold for the depth map.
        :param median: Median filter size. Can be one of 3, 5, 7, or None.
        :param extended: Whether to use extended disparity.
        :param subpixel: Whether to use subpixel disparity.
        :param lr_check: Whether to use left-right check.
        :param sigma: Sigma value for the median filter.
        :param lr_check_threshold: Threshold for the left-right check.
        """
        if depth_quality:
            depth_quality = self._set_enum_value(DepthQuality, depth_quality)
        if depth_range:
            depth_range = self._set_enum_value(DepthRange, depth_range)

        kwargs = _process_kwargs(locals())

        if len(kwargs) > 0:
            self.stereo_config = replace(self.stereo_config, **kwargs)

    @staticmethod
    def _set_enum_value(enum, value):
        if isinstance(value, str):
            return enum[value.upper()]
        elif isinstance(value, enum):
            return value
        else:
            raise ValueError(f'Invalid value: {value}')

    def _get_sdk_component(self):
        """
        Returns the DepthAI SDK stereo component.
        """
        return self.stereo_component
