from abc import abstractmethod, ABC

import robothub_depthai.device as device
from robothub_depthai import HubCamera


class Command(ABC):
    """
    The Command interface declares a method for executing a command.
    """

    def __init__(self):
        self.hub_camera = None

    def set_camera(self, hub_camera: HubCamera) -> None:
        self.hub_camera = hub_camera

    @abstractmethod
    def execute(self) -> None:
        pass

    def get_component(self):
        return None


class CreateCameraCommand(Command):
    """
    Creates a new component.
    """

    def __init__(self, camera: device.Camera) -> None:
        super().__init__()
        self._camera = camera

    def execute(self) -> None:
        camera_component = self.hub_camera.create_camera(source=self._camera.name,
                                                         resolution=self._camera.resolution,
                                                         fps=self._camera.fps)
        self._camera.camera_component = camera_component

    def get_component(self) -> device.Camera:
        return self._camera


class CreateNeuralNetworkCommand(Command):
    """
    Creates a new component.
    """

    def __init__(self, neural_network: device.NeuralNetwork) -> None:
        super().__init__()
        self._neural_network = neural_network

    def execute(self) -> None:
        neural_network = self.hub_camera.create_nn(self._neural_network.name,
                                                   self._neural_network.input.camera_component)
        self._neural_network.nn_component = neural_network

    def get_component(self) -> device.NeuralNetwork:
        return self._neural_network


class StreamCommand(Command):
    """
    Creates a new component.
    """

    def __init__(self, command) -> None:
        super().__init__()
        self._command = command

    def execute(self) -> None:
        self.hub_camera = self._command.hub_camera
        component = self._command.get_component()

        if isinstance(component, device.Camera):
            stream_component = component.camera_component
        elif isinstance(component, device.NeuralNetwork):
            stream_component = component.nn_component
        else:
            raise Exception('Component not supported for streaming, only Camera and NeuralNetwork are supported.')

        self.hub_camera.create_stream(component=stream_component,
                                      unique_key=component.stream_key,
                                      name=component.stream_name)


class CommandHistory:
    """
    The CommandHistory keeps track of executed commands.
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