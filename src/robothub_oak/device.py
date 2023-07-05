import warnings
from typing import Callable, Any, Optional, Dict, Union

from depthai import NNData

from robothub_oak.commands import (
    CreateStereoCommand, CreateCameraCommand, CreateNeuralNetworkCommand,
    StreamCommand, CommandHistory, CreateTriggerActionCommand
)
from robothub_oak.components._streamable import Streamable
from robothub_oak.components.camera import Camera
from robothub_oak.components.neural_network import NeuralNetwork
from robothub_oak.components.stereo import Stereo
from robothub_oak.hub_camera import HubCamera
from robothub_oak.trigger_action import Trigger, Action

__all__ = ['Device']


class Device:
    """
    Device represents a single device. It is used to create components and execute commands.
    Startup and shutdown of the device is handled by the DeviceManager.
    """

    def __init__(self, id: str = None, name: str = None, mxid: str = None, ip_address: str = None) -> None:
        """
        :param id: ID of the device.
        :param name: Name of the device.
        :param mxid: MXID of the device.
        :param ip_address: IP address of the device.
        """
        # Device info
        self.id = id  # device identifier provided by the user
        self.name = name  # product name
        self.mxid = mxid  # mxid of the device
        self.ip_address = ip_address  # IP address of the device

        self.cameras: Dict[str, Camera] = {}
        self.stereo: Optional[Stereo] = None
        self.neural_networks: Dict[str, NeuralNetwork] = {}

        self.hub_camera: Optional[HubCamera] = None

        # Callbacks
        self.disconnect_callback: Callable[[Any], None] = lambda x: None
        self.connect_callback: Callable[[Any], None] = lambda x: None

        self._command_history = CommandHistory()

    def __eq__(self, other):
        if isinstance(other, Device):
            return (self.id and self.id == other.id) \
                or (self.name and self.name == other.name) \
                or (self.mxid and self.mxid == other.mxid) \
                or (self.ip_address and self.ip_address == other.ip_address)
        elif isinstance(other, str):
            return self.id == other or self.name == other or self.mxid == other or self.ip_address == other
        else:
            return False

    def _start(self, hub_camera: HubCamera) -> bool:
        """
        Internal method to execute all commands.

        :param hub_camera: The HubCamera instance to use.
        :return: True if successful, False otherwise.
        """
        if hub_camera.oak_camera is None:
            return False

        self.hub_camera = hub_camera
        self._set_product_name()  # Set product name if not set

        try:
            for command in self._command_history:
                if isinstance(command, CreateStereoCommand) and not hub_camera.has_stereo:
                    warnings.warn(f'Device {self.get_device_name()} does not support stereo, skipping stereo creation.')
                    continue

                command.set_camera(hub_camera)
                command.execute()
        except Exception as e:
            warnings.warn(f'Failed to start device {self.get_device_name()} with error: {e}')
            return False

        # Create streams
        for command in self._command_history:
            # Check if stream is enabled, if so, create a stream command and execute it
            component = command.get_component()

            # Component can be None if the command failed to execute (e.g., stereo component on a single camera device)
            if isinstance(command, CreateStereoCommand) and component.stereo_component is None:
                continue

            if isinstance(component, Streamable) and component.stream_enabled:
                stream_command = StreamCommand(self, command)
                stream_command.set_camera(hub_camera)
                stream_command.execute()

        return True

    def restart(self) -> bool:
        """
        Restarts the device. This will stop all components and streams and recreate them.

        :return: True if successful, False otherwise.
        """
        try:
            if self.hub_camera:
                self.hub_camera.stop()
                self.hub_camera.oak_camera = self.hub_camera.init_oak_camera()
                self._start(hub_camera=self.hub_camera)
        except Exception as e:
            warnings.warn(f'Failed to restart device {self.get_device_name()} with error: {e}')
            return False

        return True

    def get_camera(self, name: str, resolution: str = None, fps: int = None) -> Camera:
        """
        Creates a camera component.

        :param name: The name of the camera.
        :param resolution: The resolution of the camera.
        :param fps: The FPS of the camera.
        :return: The camera.
        """
        # Check if camera already exists
        if name in self.cameras:
            return self.cameras[name]

        camera = Camera(name, resolution, fps)
        self.cameras[name] = camera

        command = CreateCameraCommand(self, camera)
        self._command_history.push(command)
        return camera

    def create_neural_network(self,
                              name: str,
                              input: Camera = None,
                              nn_type: str = None,
                              decode_fn: Callable[[NNData], Any] = None,
                              tracker: bool = False,
                              spatial: Optional[bool] = None
                              ) -> NeuralNetwork:
        """
        Creates a neural network.

        :param name: The name of the neural network.
        :param input: The input camera.
        :param nn_type: The type of neural network. Either 'yolo' or 'mobilenet'.
        :param decode_fn: The decode function to use. Decoding is done on the host.
        :param tracker: Whether to use tracking.
        :param spatial: Whether to use spatial detection.
        :return: The neural network.
        """
        if name in self.neural_networks:
            return self.neural_networks[name]
        elif not input:
            raise ValueError('Neural network must have an input')

        neural_network = NeuralNetwork(name=name,
                                       input=input,
                                       nn_type=nn_type,
                                       decode_fn=decode_fn,
                                       tracker=tracker,
                                       spatial=spatial)
        command = CreateNeuralNetworkCommand(self, neural_network)
        self._command_history.push(command)
        return neural_network

    def get_stereo_camera(self,
                          resolution: str = None,
                          fps: int = None,
                          left_camera: Camera = None,
                          right_camera: Camera = None
                          ) -> Stereo:
        """
        Creates a stereo component.

        :param resolution: The resolution of the stereo camera.
        :param fps: The FPS of the stereo camera.
        :param left_camera: The left camera.
        :param right_camera: The right camera.
        """
        if self.stereo:
            return self.stereo

        self.stereo = Stereo(resolution, fps, left_camera, right_camera)
        command = CreateStereoCommand(self, self.stereo)
        self._command_history.push(command)
        return self.stereo

    def add_trigger(self, trigger: Trigger, action: Union[Action, Callable]) -> None:
        command = CreateTriggerActionCommand(self, trigger, action)
        self._command_history.push(command)

    def set_connect_callback(self, callback: Callable[[HubCamera], None]) -> None:
        """
        Sets the callback to be called when the device connects.

        :param callback: The callback to be called when the device connects.
        """
        self.connect_callback = callback

    def set_disconnect_callback(self, callback: Callable[[HubCamera], None]) -> None:
        """
        Sets the callback to be called when the device disconnects.

        :param callback: The callback to be called when the device disconnects.
        """
        self.disconnect_callback = callback

    def get_device_name(self) -> str:
        """
        Returns the name of the device.
        """
        return self.id or self.name or self.ip_address or self.mxid

    def _set_product_name(self):
        """
        Sets the product name of the device.
        """
        if self.hub_camera and not self.name:
            self.name = self.hub_camera.info_report().get('product_name', None)
