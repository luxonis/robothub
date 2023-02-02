import logging as log
import time
from pathlib import Path
from typing import Union, Optional, Callable, Dict, Any

import depthai
import depthai as dai
import depthai_sdk
import robothub
from depthai_sdk import OakCamera

import robothub_depthai
from robothub_depthai.callbacks import get_default_color_callback, get_default_nn_callback, get_default_depth_callback
from robothub_depthai.components import CameraComponent, NNComponent, StereoComponent
from robothub_depthai.utils import try_or_default

__all__ = ['HubCamera']

ROBOTHUB_DEPTHAI_COMPONENT = Union[
    CameraComponent,
    NNComponent,
    StereoComponent
]


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
        self.state = robothub.DeviceState.UNKNOWN
        self.device_mxid = device_mxid
        self.usb_speed = usb_speed
        self.rotation = rotation
        self.id = id

        self._history = []  # Used for device recovery after reconnect
        self._components = []
        self._streams = {}
        self._stream_handles = {}

        self.oak_camera = self._init_oak_camera()
        self.available_sensors = self.oak_camera.sensors if self.oak_camera else []

    def _init_oak_camera(self) -> OakCamera:
        # try to init for 5 seconds
        start_time = time.time()
        log.info(f'Attempting to initialize camera {self.device_mxid}...')
        while True:
            try:
                camera = OakCamera(self.device_mxid, usb_speed=self.usb_speed, rotation=self.rotation)
                return camera
            except Exception as e:
                if time.time() - start_time > 5:
                    log.info(f'Failed to initialize camera {self.device_mxid} with exception: {e}.')
                    break

                time.sleep(1)

        return None

    def recover(self) -> None:
        """
        Recreates all components and re-attaches them to the camera.
        """
        new_history = []
        for h in self._history:
            f, kwargs, old_component = h
            new_component = f(**kwargs)
            new_component.apply_config_from_component(old_component)
            new_history.append((f, kwargs, new_component))

            callback = self._streams.get(old_component, None)
            stream_handle = self._stream_handles.get(old_component, None)
            if callback and stream_handle:
                self._add_stream_callback(stream_handle=stream_handle, component=new_component, callback=callback)

        self._history = new_history
        self.state = robothub.DeviceState.CONNECTED

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
        comp = robothub_depthai.CameraComponent(comp)
        self._history.append((self.create_camera, locals(), comp))
        return comp

    def create_nn(self,
                  model: Union[str, Path],
                  input: Union[depthai_sdk.components.CameraComponent, depthai_sdk.components.NNComponent],
                  nn_type: Optional[str] = None,
                  tracker: bool = False,
                  spatial: Union[None, bool, StereoComponent] = None,
                  decode_fn: Optional[Callable] = None
                  ) -> NNComponent:
        if isinstance(input, CameraComponent):
            input = input.component

        comp = self.oak_camera.create_nn(model=model, input=input, nn_type=nn_type,
                                         tracker=tracker, spatial=spatial, decode_fn=decode_fn)
        comp = NNComponent(comp)
        self._history.append((self.create_nn, locals(), comp))
        return comp

    def create_stereo(self,
                      resolution: Union[None, str, dai.MonoCameraProperties.SensorResolution] = None,
                      fps: Optional[float] = None,
                      left: Union[None, dai.Node.Output, depthai_sdk.components.CameraComponent] = None,
                      right: Union[None, dai.Node.Output, depthai_sdk.components.CameraComponent] = None,
                      ) -> StereoComponent:
        """
        Creates a stereo component.

        :param resolution: Resolution of the stereo component.
        :param fps: FPS of the output stream.
        :param left: Left camera component, optional.
        :param right: Right camera component, optional.
        """
        comp = self.oak_camera.create_stereo(resolution=resolution, fps=fps, left=left, right=right, encode='h264')
        comp = robothub_depthai.StereoComponent(comp)
        self._history.append((self.create_stereo, locals(), comp))
        return comp

    def create_stream(self,
                      component: ROBOTHUB_DEPTHAI_COMPONENT,
                      unique_key: str,
                      name: str,
                      callback: Callable = None
                      ) -> None:
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
        self._stream_handles[component] = stream_handle
        self._add_stream_callback(stream_handle=stream_handle, component=component, callback=callback)

    def _add_stream_callback(self,
                             stream_handle: robothub.StreamHandle,
                             component: ROBOTHUB_DEPTHAI_COMPONENT,
                             callback: Callable
                             ) -> None:
        if isinstance(component, CameraComponent):
            fn = callback or get_default_color_callback(stream_handle)
            self.oak_camera.callback(component.out.encoded,
                                     callback=fn)
            self._streams[component] = fn
        elif isinstance(component, NNComponent):
            fn = callback or get_default_nn_callback(stream_handle)
            self.oak_camera.callback(component.out.encoded,
                                     callback=fn)
            self._streams[component] = fn
        elif isinstance(component, StereoComponent):
            fn = callback or get_default_depth_callback(stream_handle)
            self.oak_camera.callback(component.out.encoded,
                                     callback=fn)
            self._streams[component] = fn

    def callback(self, output: Any, callback: Callable, enable_visualizer: bool = False) -> None:
        self.oak_camera.callback(output, callback=callback, enable_visualizer=enable_visualizer)

    def poll(self) -> Optional[int]:
        """
        Polls the device for new data.
        """
        return self.oak_camera.poll()

    def start(self) -> None:
        """
        Starts the device and sets the state to connected.
        """
        while not self.app.stop_event.is_set():
            try:
                self.oak_camera.start()
                self.state = robothub.DeviceState.CONNECTED
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
        """
        Returns a dictionary with statistics about the device.
        """
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
        """
        Returns a dictionary with information about the device.
        """
        info = {
            'mxid': self.device.getMxId(),
            'protocol': 'unknown',
            'platform': 'unknown',
            'product_name': 'unknown',
            'board_name': 'unknown',
            'board_rev': 'unknown',
            'bootloader_version': 'unknown',
            'state': self.state.value,
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

    @property
    def device(self) -> dai.Device:
        """
        Returns the device object.
        """
        return self.oak_camera.device

    @property
    def is_connected(self) -> bool:
        """
        Returns whether the device is connected or not.
        :return: True if connected, False otherwise.
        """
        return not self.device.isClosed()

    @property
    def has_color(self) -> bool:
        """
        Returns whether the device has a color camera.
        :return: True if the device has a color camera, False otherwise.
        """
        return depthai.CameraBoardSocket.RGB in self.available_sensors

    @property
    def has_left(self) -> bool:
        """
        Returns whether the device has a left camera.
        :return: True if the device has a left camera, False otherwise.
        """
        return depthai.CameraBoardSocket.LEFT in self.available_sensors

    @property
    def has_right(self) -> bool:
        """
        Returns whether the device has a right camera.
        :return: True if the device has a right camera, False otherwise.
        """
        return depthai.CameraBoardSocket.RIGHT in self.available_sensors

    @property
    def has_stereo(self) -> bool:
        """
        Returns whether the device has a depth camera.
        :return: True if the device has a stereo camera, False otherwise.
        """
        return self.has_left and self.has_right
