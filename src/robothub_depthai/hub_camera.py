import logging as log
import time
from pathlib import Path
from typing import Union, Optional, Callable, List

import depthai as dai
import robothub
from depthai_sdk import OakCamera, CameraComponent, StereoComponent, NNComponent
from robothub import DeviceState

from robothub_depthai.callbacks import get_default_color_callback, get_default_nn_callback


class HubCamera:
    def __init__(self,
                 app: robothub.RobotHubApplication,
                 device_mxid: str,
                 usb_speed: Union[None, str, dai.UsbSpeed] = None,
                 rotation: int = 0):
        self.app = app
        self.state = DeviceState.UNKNOWN
        self.device_mxid = device_mxid
        self.usb_speed = usb_speed
        self.rotation = rotation

        self.oak_camera = OakCamera(self.device_mxid, usbSpeed=self.usb_speed, rotation=self.rotation)
        self.available_sensors = self._get_sensor_names()  
        
    def create_camera(self,
                      source: str,
                      resolution: Union[
                          None, str, dai.ColorCameraProperties.SensorResolution, dai.MonoCameraProperties.SensorResolution
                      ] = None,
                      fps: Optional[float] = None,
                      encode: Union[None, str, bool, dai.VideoEncoderProperties.Profile] = 'h264'
                      ) -> CameraComponent:
        comp = self.oak_camera.create_camera(source=source, resolution=resolution, fps=fps, encode=encode)
        return comp

    def create_nn(self,
                  model: Union[str, Path],
                  input: Union[CameraComponent, NNComponent],
                  nn_type: Optional[str] = None,
                  tracker: bool = False,
                  spatial: Union[None, bool, StereoComponent] = None,
                  decode_fn: Optional[Callable] = None
                  ) -> NNComponent:
        comp = self.oak_camera.create_nn(model=model, input=input, nn_type=nn_type,
                                         tracker=tracker, spatial=spatial, decode_fn=decode_fn)
        return comp

    def create_stereo(self,
                      resolution: Union[None, str, dai.MonoCameraProperties.SensorResolution] = None,
                      fps: Optional[float] = None,
                      left: Union[None, dai.Node.Output, CameraComponent] = None,
                      right: Union[None, dai.Node.Output, CameraComponent] = None,
                      ) -> StereoComponent:
        comp = self.oak_camera.create_stereo(resolution=resolution, fps=fps, left=left, right=right)
        return comp

    def create_stream(self,
                      component: Union[CameraComponent, NNComponent, StereoComponent],
                      name: str,
                      description: str,
                      callback: Callable = None) -> None:
        log.debug(f'Creating stream {name} for component {component}')

        stream_handle = robothub.STREAMS.create_video(camera_serial=self.device_mxid,
                                                      unique_key=name,
                                                      description=description)

        if isinstance(component, CameraComponent):
            self.oak_camera.callback(component.out.encoded, callback=callback or get_default_color_callback(stream_handle))
        elif isinstance(component, NNComponent):
            self.oak_camera.callback(component.out.encoded, callback=callback or get_default_nn_callback(stream_handle))
            # self.oak_camera.sync([component, component.out.input], callback=callback or get_default_nn_callback(stream_handle))
        else:
            pass  # TODO other components

    def poll(self) -> None:
        self.oak_camera.poll()

    def start(self) -> None:
        while not self.app.stop_event.set():
            try:
                self.oak_camera.start()
                self.state = DeviceState.CONNECTED
                return
            except Exception as e:
                print(f'Could not start camera with exception {e}')
            
            time.sleep(1)

    def stop(self) -> None:
        self.oak_camera.device.close()

    def _connect(self, reattempt_time: int = 1) -> None:
        """
        Attempts to establish a connection with the device.
        Keeps attempting to connect forever, updates self.state accordingly
        """
        log.debug(f'Connecting to device {self.device_mxid}...')

        self.state = DeviceState.CONNECTING
        self.oak_camera = OakCamera(self.device_mxid, usbSpeed=self.usb_speed, rotation=self.rotation)
        while not self.app.stop_event.is_set():
            try:
                self.oak_camera._init_device()
                self.state = DeviceState.CONNECTED
                log.debug(f'Successfully connected to device {self.device_mxid}')
                return
            except BaseException as err:
                log.error(f'Cannot connect to device {self.device_mxid}: {err}'
                          f' - Retrying in {reattempt_time} seconds')

            self.app.stop_event.wait(timeout=reattempt_time)

    def _disconnect(self) -> None:
        """Intended to be used for a temporary disconnect to allow changing DAI pipeline etc."""
        log.debug(f'Disconnecting from device {self.device_mxid}...')
        self.state = DeviceState.DISCONNECTED
        self.oak_camera.__exit__(Exception, 'Disconnecting from device', 'placeholder')

        self.oak_camera = OakCamera(self.device_mxid, usbSpeed=self.usb_speed, rotation=self.rotation)

    def _get_sensor_names(self) -> List[str]:
        """
        Returns a list of available sensors on the device.
        :return: List of available sensors.
        """
        self._connect()
        sensors = self.oak_camera._oak.device.getCameraSensorNames()
        self._disconnect()
        return sensors

    @property
    def device(self) -> dai.Device:
        return self.oak_camera.device
