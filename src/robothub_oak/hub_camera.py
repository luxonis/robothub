import logging as log
import time
import traceback
import warnings
from pathlib import Path
from typing import Union, Optional, Callable, Dict, Any

import depthai as dai
import depthai_sdk
import robothub
from depthai_sdk import OakCamera
from depthai_sdk.components import CameraComponent, StereoComponent, NNComponent
from depthai_sdk.trigger_action import Trigger, Action

import robothub_oak
from robothub_oak.callbacks import get_default_callback
from robothub_oak.utils import try_or_default

__all__ = ['HubCamera']


class HubCamera:
    """
    Wrapper for the DepthAI OakCamera class.
    """

    def __init__(self,
                 device_name: str,
                 usb_speed: Union[None, str, dai.UsbSpeed] = None,
                 rotation: int = 0):
        """
        :param device_name: Device identifier, either mxid, IP address or USB port.
        :param usb_speed: USB speed to use.
        :param rotation: Rotation of the camera, defaults to 0.
        """
        self.state = robothub.DeviceState.UNKNOWN
        self.device_name = device_name
        self.usb_speed = usb_speed
        self.rotation = rotation

        self.stop_event = robothub.threading.Event()
        self.streams = {}  # unique_key -> StreamHandle
        self.available_sensors = []  # self.oak_camera.sensors if self.oak_camera else []

        self.oak_camera = self.init_oak_camera()

    def init_oak_camera(self) -> Optional[OakCamera]:
        """
        Initializes the OakCamera instance. Will try to initialize for 5 seconds before returning None.

        :return: OakCamera instance if successful, None otherwise.
        """
        start_time = time.time()
        while not self.stop_event.is_set():
            try:
                camera = OakCamera(self.device_name, usb_speed=self.usb_speed,
                                   rotation=self.rotation, replay=robothub_oak.REPLAY_PATH)
                if camera.replay:
                    camera.replay.set_loop(True)

                self.available_sensors = camera.sensors
                return camera
            except Exception:
                if time.time() - start_time > 10:
                    break

                self.stop_event.wait(1)

        return None

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
        :return: The camera component.
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
        """
        Creates a neural network component.

        :param model: Name or path to the model.
        :param input: Input component, either a camera or another neural network.
        :param nn_type: Either 'yolo' or 'mobilenet'. For other types, use None.
        :param tracker: If True, will enable and add a tracker to the output.
        :param spatial: If True, will enable and add spatial data to the output. If a StereoComponent is provided, will use that component to calculate the spatial data.
        :param decode_fn: Function to decode the output of the neural network.

        :return: Neural network component.
        """
        comp = self.oak_camera.create_nn(model=model, input=input, nn_type=nn_type,
                                         tracker=tracker, spatial=spatial, decode_fn=decode_fn)
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
        :return: Stereo component.
        """
        if not self.has_stereo:
            raise RuntimeError('Device does not have stereo cameras.')

        comp = self.oak_camera.create_stereo(resolution=resolution, fps=fps, left=left, right=right, encode='h264')
        return comp

    def create_stream(self,
                      component: Union[CameraComponent, NNComponent, StereoComponent],
                      unique_key: str,
                      name: str,
                      callback: Callable = None,
                      visualizer_callback: Callable = None,
                      ) -> None:
        """
        Creates a stream for the given component.

        :param component: Component to create a stream for.
        :param unique_key: Unique key for the stream.
        :param name: Name of the stream that will be used in Live View.
        :param callback: Callback function to be called when a new frame is received.
        :param visualizer_callback: Callback function to be called inside the default callback function. Mutually exclusive with callback.
        """
        if visualizer_callback and callback:
            warnings.warn(
                'visualizer_callback and callback are mutually exclusive. visualizer_callback will be ignored.'
            )

        log.debug(f'Stream: creating stream {name} for component {component}.')

        if unique_key is None:
            unique_key = f'{self.device_name}_{component.__class__.__name__.lower()}_{component.out.encoded.__name__}'

        if unique_key in robothub.STREAMS.streams.keys():
            stream_handle = robothub.STREAMS.streams[unique_key]
        else:
            stream_handle = self._create_stream(unique_key=unique_key, name=name)

        self.streams[unique_key] = stream_handle
        self._add_stream_callback(stream_handle=stream_handle,
                                  component=component,
                                  callback=callback,
                                  visualizer_callback=visualizer_callback)

    def _create_stream(self, unique_key: str, name: str) -> robothub.StreamHandle:
        try:
            return robothub.STREAMS.create_video(camera_serial=self.device_name,
                                                 unique_key=unique_key,
                                                 description=name)
        except Exception:
            robothub.STREAMS.destroy_streams_by_id([unique_key])
            return robothub.STREAMS.create_video(camera_serial=self.device_name,
                                                 unique_key=unique_key,
                                                 description=name)

    def _add_stream_callback(self,
                             stream_handle: robothub.StreamHandle,
                             component: Union[CameraComponent, NNComponent, StereoComponent],
                             callback: Callable,
                             visualizer_callback: Callable
                             ) -> None:
        """
        Selects the correct callback function for the given component and adds it to the stream.

        :param stream_handle: Stream handle to add the callback to.
        :param component: Component to create a callback for.
        :param callback: User-defined callback function to be called when a new frame is received.
        :param visualizer_callback: User-defined callback function to be called inside the default callback function. Mutually exclusive with callback.
        """
        fn = callback or get_default_callback(stream_handle, visualizer_callback=visualizer_callback)
        enable_visualizer = True if callback or visualizer_callback else None

        if fn:
            self.oak_camera.callback(component.out.encoded, callback=fn, enable_visualizer=enable_visualizer)

    def callback(self, output: Any, callback: Callable, enable_visualizer: bool = False) -> None:
        """
        Sets a callback function for the given output.

        :param output: Output to set the callback for.
        :param callback: Callback function to be called when a new frame is received.
        :param enable_visualizer: Whether to enable the visualizer that provides metadata.
        """
        self.oak_camera.callback(output, callback=callback, enable_visualizer=enable_visualizer)

    def create_trigger(self, trigger: Trigger, action: Union[Action, Callable]):
        self.oak_camera.trigger_action(trigger, action)

    def poll(self) -> Optional[int]:
        """
        Polls the device for new data.
        """
        return self.oak_camera.poll()

    def start(self) -> bool:
        """
        Starts the device and sets the state to connected.
        """
        if self.state == robothub.DeviceState.CONNECTED:
            return True

        start_time = time.monotonic()
        while not self.stop_event.is_set():
            try:
                self.oak_camera.start()
                self.state = robothub.DeviceState.CONNECTED
                return True
            except Exception as e:
                if time.monotonic() - start_time > 10:
                    return False

                log.debug(traceback.print_exc())
                warnings.warn(f'Camera: could not start with exception {e}.')

            self.stop_event.wait(1)

    def stop(self) -> None:
        """
        Stops the device and sets the state to disconnected.
        """
        self.stop_event.set()

        for stream in self.streams.values():
            try:
                robothub.STREAMS.destroy(stream)
            except ValueError:
                pass

        self.streams.clear()
        self.state = robothub.DeviceState.DISCONNECTED

        if self.oak_camera:
            self.oak_camera.device.close()

        self.oak_camera = None
        self.available_sensors = []

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

        bootloader_version = self.device.getBootloaderVersion()  # can be None
        if bootloader_version:
            info['bootloader_version'] = bootloader_version.toStringSemver()

        if eeprom_data:
            info['product_name'] = eeprom_data.productName
            info['board_name'] = eeprom_data.boardName
            info['board_rev'] = eeprom_data.boardRev

        if device_info:
            info['protocol'] = device_info.protocol.name
            info['platform'] = device_info.platform.name

        return info

    @property
    def device(self) -> dai.Device:
        """
        Returns the device object.
        :return: depthai.Device object.
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
        return dai.CameraBoardSocket.RGB in self.available_sensors

    @property
    def has_left(self) -> bool:
        """
        Returns whether the device has a left camera.
        :return: True if the device has a left camera, False otherwise.
        """
        return dai.CameraBoardSocket.LEFT in self.available_sensors

    @property
    def has_right(self) -> bool:
        """
        Returns whether the device has a right camera.
        :return: True if the device has a right camera, False otherwise.
        """
        return dai.CameraBoardSocket.RIGHT in self.available_sensors

    @property
    def has_stereo(self) -> bool:
        """
        Returns whether the device has a depth camera.
        :return: True if the device has a stereo camera, False otherwise.
        """
        return self.has_left and self.has_right
