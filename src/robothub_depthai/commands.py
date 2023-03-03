from abc import abstractmethod, ABC

from robothub_depthai.components.camera import Camera
from robothub_depthai.components.neural_network import NeuralNetwork
from robothub_depthai.components.stereo import Stereo
from robothub_depthai.hub_camera import HubCamera

__all__ = [
    'CreateCameraCommand', 'CreateNeuralNetworkCommand', 'CreateStereoCommand',
    'StreamCommand', 'CommandHistory'
]


class Command(ABC):
    """
    The Command interface declares a method for executing a command.
    """

    def __init__(self):
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

    def __init__(self, camera: Camera) -> None:
        super().__init__()
        self._camera = camera

    def execute(self) -> None:
        camera_component = self.hub_camera.create_camera(source=self._camera.name,
                                                         resolution=self._camera.resolution,
                                                         fps=self._camera.fps)
        self._camera.camera_component = camera_component

    def get_component(self) -> Camera:
        return self._camera


class CreateNeuralNetworkCommand(Command):
    """
    Creates a new neural network component.
    """

    def __init__(self, neural_network: NeuralNetwork) -> None:
        super().__init__()
        self._neural_network = neural_network

    def execute(self) -> None:
        neural_network = self.hub_camera.create_nn(self._neural_network.name,
                                                   self._neural_network.input.camera_component)
        self._neural_network.nn_component = neural_network

    def get_component(self) -> NeuralNetwork:
        return self._neural_network


class CreateStereoCommand(Command):
    """
    Creates a new stereo component.
    """

    def __init__(self, stereo: Stereo) -> None:
        super().__init__()
        self._stereo = stereo

    def execute(self) -> None:
        stereo_component = self.hub_camera.create_stereo(resolution=self._stereo.resolution, fps=self._stereo.fps)
        self._stereo.stereo_component = stereo_component

    def get_component(self) -> Stereo:
        return self._stereo


class StreamCommand(Command):
    """
    Creates a new stream.
    """

    def __init__(self, command) -> None:
        super().__init__()
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
