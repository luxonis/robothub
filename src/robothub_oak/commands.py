from abc import abstractmethod, ABC
from dataclasses import asdict
from typing import Callable

import depthai_sdk.classes.packets as packets

from robothub_oak.components.camera import Camera
from robothub_oak.components.neural_network import NeuralNetwork
from robothub_oak.components.stereo import Stereo
from robothub_oak.hub_camera import HubCamera
from robothub_oak.packets import HubPacket, DetectionPacket, TrackerPacket, DepthPacket, IMUPacket

__all__ = [
    'CreateCameraCommand',
    'CreateNeuralNetworkCommand',
    'CreateStereoCommand',
    'StreamCommand',
    'CommandHistory'
]


class Command(ABC):
    """
    The Command interface declares a method for executing a command.
    """

    def __init__(self, device: 'Device'):
        self.device = device
        self.hub_camera = None

    @abstractmethod
    def execute(self) -> None:
        pass

    def set_camera(self, hub_camera: HubCamera) -> None:
        self.hub_camera = hub_camera

    def get_component(self):
        return None


class CreateCameraCommand(Command):
    """
    Creates a new camera component.
    """

    def __init__(self, device: 'Device', camera: Camera) -> None:
        super().__init__(device=device)
        self._camera = camera

    def execute(self) -> None:
        camera_component = self.hub_camera.create_camera(source=self._camera.name,
                                                         resolution=self._camera.resolution,
                                                         fps=self._camera.fps)
        camera_component.config_color_camera(**asdict(self._camera.camera_config))

        self._camera.camera_component = camera_component

    def get_component(self) -> Camera:
        return self._camera


class CreateNeuralNetworkCommand(Command):
    """
    Creates a new neural network component.
    """

    def __init__(self, device: 'Device', neural_network: NeuralNetwork) -> None:
        super().__init__(device=device)
        self._neural_network = neural_network

    def execute(self) -> None:
        nn_component = self.hub_camera.create_nn(model=self._neural_network.name,
                                                 input=self._neural_network.input.camera_component,
                                                 nn_type=self._neural_network.nn_type,
                                                 tracker=self._neural_network.tracker,
                                                 spatial=self._neural_network.spatial,
                                                 decode_fn=self._neural_network.decode_fn)

        for callback in self._neural_network.callbacks:
            self.hub_camera.callback(nn_component, self._callback_wrapper(callback), True)

        self._neural_network.nn_component = nn_component

    def get_component(self) -> NeuralNetwork:
        return self._neural_network

    def _callback_wrapper(self, callback: Callable) -> Callable[[HubPacket], None]:
        """
        Wraps the callback to be called with a HubPacket.
        :param callback: The callback to be wrapped.
        :return: The wrapped callback.
        """

        def __determine_packet_type(packet) -> Callable:
            packet_type = type(packet)
            if packet_type is packets.DetectionPacket:
                return DetectionPacket
            elif packet_type is packets.TrackerPacket:
                return TrackerPacket
            elif packet_type is packets.DepthPacket:
                return DepthPacket
            elif packet_type is packets.IMUPacket:
                return IMUPacket
            else:
                return HubPacket

        def callback_wrapper(packet):
            callback(__determine_packet_type(packet)(device=self.device, packet=packet))

        return callback_wrapper


class CreateStereoCommand(Command):
    """
    Creates a new stereo component.
    """

    def __init__(self, device: 'Device', stereo: Stereo) -> None:
        super().__init__(device=device)
        self._stereo = stereo

    def execute(self) -> None:
        left = self._stereo.left_camera.camera_component if self._stereo.left_camera else None
        right = self._stereo.right_camera.camera_component if self._stereo.right_camera else None
        stereo_component = self.hub_camera.create_stereo(resolution=self._stereo.resolution,
                                                         fps=self._stereo.fps,
                                                         left=left,
                                                         right=right)
        self._stereo.stereo_component = stereo_component

    def get_component(self) -> Stereo:
        return self._stereo


class StreamCommand(Command):
    """
    Creates a new stream.
    """

    def __init__(self, device: 'Device', command: 'Command') -> None:
        super().__init__(device=device)
        self._command = command

    def execute(self) -> None:
        component = self._command.get_component()

        if isinstance(component, Camera):
            stream_component = component.camera_component
        elif isinstance(component, NeuralNetwork):
            stream_component = component.nn_component
        elif isinstance(component, Stereo):
            stream_component = component.stereo_component
        else:
            raise Exception('Component not supported for streaming, only Camera and NeuralNetwork are supported.')

        self.hub_camera.create_stream(component=stream_component,
                                      unique_key=component.stream_key,
                                      name=component.stream_name)


class CommandHistory:
    """
    The CommandHistory keeps track of the created commands.
    """

    def __init__(self) -> None:
        self._commands = []

    def push(self, command: Command) -> None:
        """
        Adds a command to the history.
        """
        self._commands.append(command)

    def pop(self) -> Command:
        """
        Removes the last command from the history.
        """
        return self._commands.pop()

    def __len__(self) -> int:
        return len(self._commands)

    def __iter__(self):
        return iter(self._commands)
