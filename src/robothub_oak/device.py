import warnings
from typing import Callable, Any, Optional

from depthai import NNData

from robothub_oak.commands import (
    CreateStereoCommand, CreateCameraCommand, CreateNeuralNetworkCommand,
    StreamCommand, CommandHistory
)
from robothub_oak.components.camera import Camera
from robothub_oak.components.neural_network import NeuralNetwork
from robothub_oak.components.stereo import Stereo
from robothub_oak.components.streamable import Streamable
from robothub_oak.hub_camera import HubCamera

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
        self.id = id
        self.name = name
        self.mxid = mxid
        self.ip_address = ip_address

        # Callbacks
        self.disconnect_callback = lambda x: None  # type: Callable[[Any], None]
        self.connect_callback = lambda x: None  # type: Callable[[Any], None]

        self._command_history = CommandHistory()

    def _start(self, hub_camera: HubCamera) -> bool:
        """
        Internal method to execute all commands.

        :param hub_camera: The HubCamera instance to use.
        :return: True if successful, False otherwise.
        """
        if hub_camera.oak_camera is None:
            return False

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

    def get_camera(self, name: str, resolution: str, fps: int) -> Camera:
        """
        Creates a camera component.

        :param name: The name of the camera.
        :param resolution: The resolution of the camera.
        :param fps: The FPS of the camera.
        :return: The camera.
        """
        camera = Camera(name, resolution, fps)
        command = CreateCameraCommand(self, camera)
        self._command_history.push(command)
        return camera

    def create_neural_network(self,
                              name: str,
                              input: Camera,
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
        if isinstance(input, NeuralNetwork):
            raise NotImplementedError('Neural networks cannot be used as input for other neural networks yet')

        neural_network = NeuralNetwork(name=name, input=input, nn_type=nn_type, decode_fn=decode_fn,
                                       tracker=tracker, spatial=spatial)
        command = CreateNeuralNetworkCommand(self, neural_network)
        self._command_history.push(command)
        return neural_network

    def get_stereo_camera(self, resolution: str, fps: int, left_camera: Camera = None, right_camera: Camera = None):
        """
        Creates a stereo component.

        :param resolution: The resolution of the stereo camera.
        :param fps: The FPS of the stereo camera.
        """
        stereo = Stereo(resolution, fps, left_camera, right_camera)
        command = CreateStereoCommand(self, stereo)
        self._command_history.push(command)
        return stereo

    def set_connect_callback(self, callback: Callable[[HubCamera], None]) -> None:
        """
        Sets the callback to be called when the device connects.

        :param callback: The callback to be called when the device connects.
        :return: None
        """
        self.connect_callback = callback

    def set_disconnect_callback(self, callback: Callable[[HubCamera], None]) -> None:
        """
        Sets the callback to be called when the device disconnects.

        :param callback: The callback to be called when the device disconnects.
        :return: None
        """
        self.disconnect_callback = callback

    def get_device_name(self):
        return self.id or self.name or self.mxid or self.ip_address
