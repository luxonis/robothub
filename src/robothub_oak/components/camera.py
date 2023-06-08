from dataclasses import dataclass, replace
from typing import Optional, Tuple, Union

import depthai as dai

from robothub_oak.components._component import Component
from robothub_oak.components.streamable import Streamable
from robothub_oak.utils import _process_kwargs

__all__ = ['Camera']


@dataclass
class CameraConfig:
    """
    Dataclass representing the configuration of the camera.
    """
    interleaved: Optional[bool] = None
    color_order: Union[None, dai.ColorCameraProperties.ColorOrder, str] = None
    manual_focus: Optional[int] = None
    af_mode: Optional[dai.CameraControl.AutoFocusMode] = None
    awb_mode: Optional[dai.CameraControl.AutoWhiteBalanceMode] = None
    scene_mode: Optional[dai.CameraControl.SceneMode] = None
    anti_banding_mode: Optional[dai.CameraControl.AntiBandingMode] = None
    effect_mode: Optional[dai.CameraControl.EffectMode] = None
    isp_scale: Optional[Tuple[int, int]] = None
    sharpness: Optional[int] = None
    luma_denoise: Optional[int] = None
    chroma_denoise: Optional[int] = None


class Camera(Component, Streamable):
    """
    This component represents a single camera on the OAK, either color or mono one.
    The API provides a way to configure the camera, but it is not required to do so.
    """

    def __init__(self, name: str, resolution: Optional[str], fps: Optional[int]) -> None:
        Component.__init__(self)
        Streamable.__init__(self)
        self.name = name
        self.resolution = resolution
        self.fps = fps

        self.camera_component = None  # type: depthai_sdk.components.CameraComponent
        self.camera_config = CameraConfig()

    def configure(self,
                  interleaved: Optional[bool] = None,
                  color_order: Union[None, dai.ColorCameraProperties.ColorOrder, str] = None,
                  # Cam control
                  manual_focus: Optional[int] = None,
                  af_mode: Optional[dai.CameraControl.AutoFocusMode] = None,
                  awb_mode: Optional[dai.CameraControl.AutoWhiteBalanceMode] = None,
                  scene_mode: Optional[dai.CameraControl.SceneMode] = None,
                  anti_banding_mode: Optional[dai.CameraControl.AntiBandingMode] = None,
                  effect_mode: Optional[dai.CameraControl.EffectMode] = None,
                  # IQ settings
                  isp_scale: Optional[Tuple[int, int]] = None,
                  sharpness: Optional[int] = None,
                  luma_denoise: Optional[int] = None,
                  chroma_denoise: Optional[int] = None,
                  ) -> None:
        """
        Configures the camera component.
        """
        kwargs = _process_kwargs(locals())

        if len(kwargs) > 0:
            self.camera_config = replace(self.camera_config, **kwargs)

    def set_resolution(self, resolution: str) -> None:
        """
        Sets the resolution of the camera.

        :param resolution: String representation of the resolution, e.g. '1080p' or '4K'.
        """
        self.resolution = resolution

    def set_fps(self, fps: int) -> None:
        """
        Sets the FPS of the camera.

        :param fps: FPS to set as an integer.
        """
        self.fps = fps
