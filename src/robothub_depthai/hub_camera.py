import contextlib
import logging as log
import os
import time
from pathlib import Path
from typing import Union, Optional, Callable, List, Dict, Any

import depthai as dai
import robothub
from depthai_sdk import OakCamera, CameraComponent, StereoComponent, NNComponent
from robothub import DeviceState

from robothub_depthai.callbacks import get_default_color_callback, get_default_nn_callback, get_default_depth_callback
from robothub_depthai.utils import try_or_default

__all__ = ['HubCamera']


class HubCamera:
    """
    Wrapper for the DepthAI OakCamera class.
    """

    def __init__(self,
                 app: robothub.RobotHubApplication,
                 device_mxid: str,
                 id: int,
                 usb_speed: Union[None, str, dai.UsbSpeed] = None,
                 rotation: int = 0):
        """
        :param app: RobotHubApplication instance.
        :param device_mxid: MXID of the device.
        :param usb_speed: USB speed to use.
        :param rotation: Rotation of the camera, defaults to 0.
        """
        self.app = app
        self.state = DeviceState.UNKNOWN
        self.device_mxid = device_mxid
        self.usb_speed = usb_speed
        self.rotation = rotation
        self.id = id

        self.oak_camera = OakCamera(self.device_mxid, usbSpeed=self.usb_speed, rotation=self.rotation)
        self.available_sensors = self._get_sensor_names()

    def create_camera(self,
                      source: str,
                      resolution: Union[
                          None, str, dai.ColorCameraProperties.SensorResolution, dai.MonoCameraProperties.SensorResolution
                      ] = None,
                      fps: Optional[float] = None
                      ) -> CameraComponent:
        """
        Creates a camera component.

        :param source: Source of the camera. Can be either 'color', 'left', 'right' or a sensor name.
        :param resolution: Resolution of the camera.
        :param fps: FPS of the output stream.
        """
        comp = self.oak_camera.create_camera(source=source, resolution=resolution, fps=fps, encode='h264')
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
        """
        Creates a stereo component.

        :param resolution: Resolution of the stereo component.
        :param fps: FPS of the output stream.
        :param left: Left camera component, optional.
        :param right: Right camera component, optional.
        """
        comp = self.oak_camera.create_stereo(resolution=resolution, fps=fps, left=left, right=right, encode='h264')
        return comp

    def create_stream(self,
                      component: Union[CameraComponent, NNComponent, StereoComponent],
                      unique_key: str,
                      name: str,
                      callback: Callable = None) -> None:
        """
        Creates a stream for the given component.

        :param component: Component to create a stream for.
        :param unique_key: Unique key for the stream.
        :param name: Name of the stream that will be used in Live View.
        :param callback: Callback function to be called when a new frame is received.
        """
        log.debug(f'Creating stream {name} for component {component}')

        stream_handle = robothub.STREAMS.create_video(camera_serial=self.device_mxid,
                                                      unique_key=unique_key,
                                                      description=name)

        if isinstance(component, CameraComponent):
            self.oak_camera.callback(component.out.encoded,
                                     callback=callback or get_default_color_callback(stream_handle))
        elif isinstance(component, NNComponent):
            self.oak_camera.callback(component.out.encoded,
                                     callback=callback or get_default_nn_callback(stream_handle))
        elif isinstance(component, StereoComponent):
            self.oak_camera.callback(component.out.encoded,
                                     callback=callback or get_default_depth_callback(stream_handle))

    def callback(self, output: Any, callback: Callable):
        self.oak_camera.callback(output, callback=callback)

    def poll(self) -> None:
        """
        Polls the device for new data.
        """
        self.oak_camera.poll()

    def start(self) -> None:
        """
        Starts the device and sets the state to connected.
        """
        while not self.app.stop_event.set():
            try:
                self.oak_camera.start()
                self.state = DeviceState.CONNECTED
                return
            except Exception as e:
                print(f'Could not start camera with exception {e}')

            time.sleep(1)

    def stop(self) -> None:
        """
        Stops the device and sets the state to disconnected.
        """
        self.oak_camera.device.close()

    def stats_report(self) -> Dict[str, Any]:
        stats = {'mxid': self.device.getMxId()}

        css_cpu_usage = self.device.getLeonCssCpuUsage().average
        mss_cpu_usage = self.device.getLeonMssCpuUsage().average
        cmx_mem_usage = self.device.getCmxMemoryUsage()
        ddr_mem_usage = self.device.getDdrMemoryUsage()
        chip_temp = self.device.getChipTemperature()

        stats['css_usage'] = int(100 * css_cpu_usage)
        stats['mss_usage'] = int(100 * mss_cpu_usage)
        stats['ddr_mem_free'] = int(ddr_mem_usage.total - ddr_mem_usage.used)
        stats['ddr_mem_total'] = int(ddr_mem_usage.total)
        stats['cmx_mem_free'] = int(cmx_mem_usage.total - cmx_mem_usage.used)
        stats['cmx_mem_total'] = int(cmx_mem_usage.total)
        stats['css_temp'] = int(100 * chip_temp.css)
        stats['mss_temp'] = int(100 * chip_temp.mss)
        stats['upa_temp'] = int(100 * chip_temp.upa)
        stats['dss_temp'] = int(100 * chip_temp.dss)
        stats['temp'] = int(100 * chip_temp.average)

        return stats

    def info_report(self) -> Dict[str, Any]:
        """Returns device info"""
        info = {
            'mxid': self.device.getMxId(),
            'protocol': 'unknown',
            'platform': 'unknown',
            'product_name': 'unknown',
            'board_name': 'unknown',
            'board_rev': 'unknown',
            'bootloader_version': 'unknown',
        }

        device_info = try_or_default(self.device.getDeviceInfo)
        calibration = try_or_default(self.device.readFactoryCalibration) or try_or_default(self.device.readCalibration2)
        eeprom_data = try_or_default(calibration.getEepromData)

        if eeprom_data:
            info['product_name'] = eeprom_data.productName
            info['board_name'] = eeprom_data.boardName
            info['board_rev'] = eeprom_data.boardRev
            info['bootloader_version'] = str(eeprom_data.version)

        if device_info:
            info['protocol'] = device_info.protocol.name
            info['platform'] = device_info.platform.name

        return info

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
        """
        Intended to be used for a temporary disconnect to allow changing DAI pipeline etc.
        """
        log.debug(f'Disconnecting from device {self.device_mxid}...')
        self.state = DeviceState.DISCONNECTED
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                self.oak_camera.__exit__(Exception, 'Disconnecting device', 'placeholder')

        self.oak_camera = OakCamera(self.device_mxid, usbSpeed=self.usb_speed, rotation=self.rotation)

    def _get_sensor_names(self) -> List[str]:
        """
        Returns a list of available sensors on the device.

        :return: List of available sensors.
        """
        self._connect()
        if self.state == DeviceState.CONNECTED:
            # If device connected, get sensor names
            sensors = self.oak_camera._oak.device.getCameraSensorNames()
            self._disconnect()
            return sensors
        else:
            return []

    @property
    def device(self) -> dai.Device:
        """
        Returns the device object.
        """
        return self.oak_camera.device
