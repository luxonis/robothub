from typing import Callable, Union

import depthai_sdk

from robothub_depthai import CAMERA_MANAGER
from robothub_depthai.commands import CommandHistory, CreateCameraCommand, CreateNeuralNetworkCommand, StreamCommand

DEVICES = []


class Streamable:
    def __init__(self) -> None:
        self.stream_enabled = False
        self.stream_name = None
        self.stream_key = None

    def stream_to_hub(self, name: str, unique_key: str = None) -> None:
        self.stream_enabled = True
        self.stream_name = name
        self.stream_key = unique_key


class Camera(Streamable):
    def __init__(self, name: str, resolution: str, fps: int) -> None:
        super().__init__()
        self.name = name
        self.resolution = resolution
        self.fps = fps

        self.camera_component = None  # type: depthai_sdk.components.CameraComponent


class NeuralNetwork(Streamable):
    def __init__(self, name: str, input: Union[Camera, 'NeuralNetwork']):
        super().__init__()
        self.name = name
        self.input = input

        self.nn_component = None  # type: depthai_sdk.components.NNComponent
        self.callback = None

    def set_callback(self, callback: Callable) -> None:
        self.callback = callback


class Device:
    def __init__(self, id: str, name: str, mxid: str, ip_address: str) -> None:
        self.id = id
        self.name = name
        self.mxid = mxid
        self.ip_address = ip_address

        self.command_history = CommandHistory()

    def start(self) -> None:
        """
        Starts the device.
        """
        for command in self.command_history:
            command.execute()

            # Check if stream is enabled, if so, create a stream command and execute it
            if isinstance(command, Streamable) and command.stream_enabled:
                stream_command = StreamCommand(command)
                self.command_history.push(stream_command)
                stream_command.execute()

    def get_camera(self, name: str, resolution: str, fps: int) -> 'Camera':
        """
        Returns a Camera instance by its ID.
        """
        camera = Camera(name, resolution, fps)
        command = CreateCameraCommand(camera)
        self.command_history.push(command)
        return camera

    def create_neural_network(self, name: str, input: 'Camera') -> 'NeuralNetwork':
        """
        Creates a neural network.
        """
        neural_network = NeuralNetwork(name, input)
        command = CreateNeuralNetworkCommand(neural_network)
        self.command_history.push(command)
        return neural_network

    def set_disconnect_callback(self, callback: Callable) -> None:
        pass

    def set_connect_callback(self, callback: Callable) -> None:
        pass


def get_device(id: str = None, name: str = None, mxid: str = None, ip_address: str = None):
    """
    Returns a Device instance.
    """
    device = Device(id, name, mxid, ip_address)
    CAMERA_MANAGER.add_device(device)
    return Device(id, name, mxid, ip_address)


def get_devices():
    return DEVICES


def start_devices():
    for device in DEVICES:
        device.start()

# device,

# class App(robothub_depthai.RobotHubApplication):
#     def on_start(self):
#         device = get_device(id='oak-d-pro-1')
#
#         color = device.get_camera('color', resolution='1080p', fps=30)
#         color.stream_to_hub(name='Color stream')
#
#         # Neural network
#         neural_network = device.create_neural_network('person-detection-retail-0013', input=color)
#         neural_network.set_callback(self.on_detected_person)
#
#         # Stream neural network output to hub
#         neural_network.stream_to_hub(name='Detections stream')
#
#     def start_execution(self):
#         self.on_start()
#         start_devices()
#
#     def on_detected_person(self, packet):
#         packet.upload_as_detection(name='Detected person')
