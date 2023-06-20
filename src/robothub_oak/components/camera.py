from dataclasses import dataclass, replace
from typing import Optional, Tuple, Union

import depthai as dai
import depthai_sdk.components

from robothub_oak.components._component import Component
from robothub_oak.components._streamable import Streamable
from robothub_oak.utils import _process_kwargs, _get_methods_by_class, _convert_to_enum

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


@dataclass
class EncoderConfig:
    h26x_rate_control_mode: Optional[str] = None  # dai.VideoEncoderProperties.RateControlMode
    h26x_keyframe_freq: Optional[int] = None
    h26x_bitrate_kbps: Optional[int] = None
    h26x_num_b_frames: Optional[int] = None
    mjpeg_quality: Optional[int] = None
    mjpeg_lossless: bool = False

    def get_h26x_config(self):
        return {
            'rate_control_mode': self.h26x_rate_control_mode,
        }


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

        self.camera_component: Optional[depthai_sdk.components.CameraComponent] = None
        self.camera_config = CameraConfig()
        self.encoder_config = EncoderConfig()

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

    def configure_encoder(self,
                          h26x_rate_control_mode: Optional[
                              Union[dai.VideoEncoderProperties.RateControlMode, str]] = None,
                          h26x_keyframe_freq: Optional[int] = None,
                          h26x_bitrate_kbps: Optional[int] = None,
                          h26x_num_b_frames: Optional[int] = None,
                          mjpeg_quality: Optional[int] = None,
                          mjpeg_lossless: Optional[bool] = None
                          ) -> None:
        """
        Configures the video encoder.
        """
        kwargs = _process_kwargs(locals())

        if h26x_rate_control_mode is not None:
            h26x_rate_control_mode = _convert_to_enum(h26x_rate_control_mode,
                                                      dai.VideoEncoderProperties.RateControlMode)

        if len(kwargs) > 0:
            self.encoder_config = replace(self.encoder_config, **kwargs)

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

    def set_valid_output_types(self) -> None:
        self._valid_output_types = _get_methods_by_class(depthai_sdk.components.CameraComponent.Out)

    def _get_sdk_component(self):
        """
        Returns the DepthAI SDK camera component.
        :return:
        """
        return self.camera_component
