from dataclasses import dataclass, replace
from typing import Optional, Tuple, Union, Any, Dict

import depthai as dai

from robothub_oak.components.streamable import Streamable

__all__ = ['Camera']


@dataclass
class CameraConfig:
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


class Camera(Streamable):
    def __init__(self, name: str, resolution: str, fps: int) -> None:
        super().__init__()
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
                  ):
        kwargs = self._process_kwargs(locals())

        if len(kwargs) > 0:
            self.camera_config = replace(self.camera_config, **kwargs)

    @staticmethod
    def _process_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Process the kwargs and remove all None values."""
        kwargs.pop('self')
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        return kwargs
