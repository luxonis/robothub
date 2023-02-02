from typing import Union, Optional, Tuple

import depthai as dai
import depthai_sdk


class CameraComponent:
    def __init__(self, component: depthai_sdk.components.CameraComponent):
        self.component = component

        self.fps = None
        self.resolution = None
        self.size = None
        self.interleaved = None
        self.color_order = None
        self.manual_focus = None
        self.af_mode = None
        self.awb_mode = None
        self.scene_mode = None
        self.anti_banding_mode = None
        self.effect_mode = None
        self.isp_scale = None
        self.sharpness = None
        self.luma_denoise = None
        self.chroma_denoise = None

    def apply_config_from_component(self, component: 'CameraComponent'):
        """
        Applies configuration from another CameraComponent instance. Used after reconnecting the device.
        """
        self.config_camera(component.fps, component.resolution)
        self.config_color_camera(
            component.size, component.interleaved, component.color_order, component.manual_focus, component.af_mode,
            component.awb_mode, component.scene_mode, component.anti_banding_mode, component.effect_mode,
            component.isp_scale, component.sharpness, component.luma_denoise, component.chroma_denoise
        )

    def config_camera(self,
                      fps: Optional[float] = None,
                      resolution: Optional[Union[
                          str, dai.ColorCameraProperties.SensorResolution, dai.MonoCameraProperties.SensorResolution
                      ]] = None
                      ) -> None:
        self.component.config_camera(fps, resolution)

        self.fps = fps
        self.resolution = resolution

    def config_color_camera(self,
                            size: Optional[Tuple[int, int]] = None,
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
        self.component.config_color_camera(size, interleaved, color_order, manual_focus, af_mode,
                                           awb_mode, scene_mode, anti_banding_mode, effect_mode, isp_scale,
                                           sharpness, luma_denoise, chroma_denoise)

        self.size = size
        self.interleaved = interleaved
        self.color_order = color_order
        self.manual_focus = manual_focus
        self.af_mode = af_mode
        self.awb_mode = awb_mode
        self.scene_mode = scene_mode
        self.anti_banding_mode = anti_banding_mode
        self.effect_mode = effect_mode
        self.isp_scale = isp_scale
        self.sharpness = sharpness
        self.luma_denoise = luma_denoise
        self.chroma_denoise = chroma_denoise

    @property
    def out(self):
        return self.component.out
