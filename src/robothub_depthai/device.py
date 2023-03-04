import logging
from typing import Callable, Any

from depthai import NNData

from robothub_depthai import HubCamera
from robothub_depthai.commands import (
    CreateStereoCommand, CreateCameraCommand, CreateNeuralNetworkCommand,
    StreamCommand, CommandHistory
)
from robothub_depthai.components.camera import Camera
from robothub_depthai.components.neural_network import NeuralNetwork
from robothub_depthai.components.stereo import Stereo
from robothub_depthai.components.streamable import Streamable
from robothub_depthai.manager import DEVICE_MANAGER

__all__ = ['Device', 'get_device']


class Device:
    def __init__(self, id: str, name: str, mxid: str, ip_address: str) -> None:
        self.id = id
        self.name = name
        self.mxid = mxid
        self.ip_address = ip_address

        self.command_history = CommandHistory()

    def _start(self, hub_camera) -> bool:
        """
        Internal method to execute all commands.

        :param hub_camera: The HubCamera instance to use.
        :return: True if successful, False otherwise.
        """
        try:
            for command in self.command_history:
                command.set_camera(hub_camera)
                command.execute()

                # Check if stream is enabled, if so, create a stream command and execute it
                component = command.get_component()
                if isinstance(component, Streamable) and component.stream_enabled:
                    stream_command = StreamCommand(command)
                    stream_command.set_camera(hub_camera)
                    stream_command.execute()

        except Exception as e:
            logging.info(f'Failed to start device with error: {e}')
            return False

        return True

    def get_camera(self, name: str, resolution: str, fps: int) -> Camera:
        """
        Returns a Camera instance by its ID.
        """
        camera = Camera(name, resolution, fps)
        command = CreateCameraCommand(camera)
        self.command_history.push(command)
        return camera

    def create_neural_network(self,
                              name: str,
                              input: Camera,
                              fps: int = 30,
                              nn_type: str = None,
                              decode_fn: Callable[[NNData], Any] = None,
                              tracker: bool = None,
                              spatial: bool = False
                              ) -> NeuralNetwork:
        """
        Creates a neural network.

        :param name: The name of the neural network.
        :param input: The input camera.
        :param fps: The FPS of the neural network.
        :param nn_type: The type of neural network. Either 'yolo' or 'mobilenet'.
        :param decode_fn: The decode function to use. Decoding is done on the host.
        :param tracker: Whether to use tracking.
        :param spatial: Whether to use spatial detection.
        :return: The neural network.
        """
        if isinstance(input, NeuralNetwork):
            raise NotImplementedError('Neural networks cannot be used as input for other neural networks yet')

        neural_network = NeuralNetwork(name=name, input=input, fps=fps, nn_type=nn_type, decode_fn=decode_fn,
                                       tracker=tracker, spatial=spatial)
        command = CreateNeuralNetworkCommand(neural_network)
        self.command_history.push(command)
        return neural_network

    def get_stereo_camera(self, resolution: str, fps: int, left_camera: Camera = None, right_camera: Camera = None):
        """
        Creates a stereo component.
        """
        stereo = Stereo(resolution, fps)
        command = CreateStereoCommand(stereo)
        self.command_history.push(command)
        return stereo

    def set_disconnect_callback(self, callback: Callable) -> None:
        pass

    def set_connect_callback(self, callback: Callable) -> None:
        pass


def get_device(id: str = None, name: str = None, mxid: str = None, ip_address: str = None):
    """
    Returns a Device instance.
    """
    device = Device(id, name, mxid, ip_address)
    DEVICE_MANAGER.add_device(device)
    return device
