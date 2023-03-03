from typing import Callable

from robothub_depthai.commands import CommandHistory, CreateCameraCommand, CreateNeuralNetworkCommand, StreamCommand, \
    CreateStereoCommand
from robothub_depthai.components import Streamable, Stereo
from robothub_depthai.components.camera import Camera
from robothub_depthai.components.neural_network import NeuralNetwork
from robothub_depthai.manager import DEVICE_MANAGER

__all__ = ['Device', 'get_device']


class Device:
    def __init__(self, id: str, name: str, mxid: str, ip_address: str) -> None:
        self.id = id
        self.name = name
        self.mxid = mxid
        self.ip_address = ip_address

        self.command_history = CommandHistory()

    def _start(self, hub_camera) -> None:
        """
        Internal method to execute all commands.
        """
        for command in self.command_history:
            command.set_camera(hub_camera)
            command.execute()

            # Check if stream is enabled, if so, create a stream command and execute it
            component = command.get_component()
            if isinstance(component, Streamable) and component.stream_enabled:
                stream_command = StreamCommand(command)
                stream_command.set_camera(hub_camera)
                stream_command.execute()

    def get_camera(self, name: str, resolution: str, fps: int) -> Camera:
        """
        Returns a Camera instance by its ID.
        """
        camera = Camera(name, resolution, fps)
        command = CreateCameraCommand(camera)
        self.command_history.push(command)
        return camera

    def create_neural_network(self, name: str, input: Camera) -> NeuralNetwork:
        """
        Creates a neural network.
        """
        neural_network = NeuralNetwork(name, input)
        command = CreateNeuralNetworkCommand(neural_network)
        self.command_history.push(command)
        return neural_network

    def create_stereo(self, resolution: str, fps: int, left_camera: Camera, right_camera: Camera):
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
