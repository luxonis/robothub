from typing import Union, Callable

from robothub_depthai.components import Streamable, Camera

__all__ = ['NeuralNetwork']


class NeuralNetwork(Streamable):
    def __init__(self, name: str, input: Union[Camera, 'NeuralNetwork']):
        super().__init__()
        self.name = name
        self.input = input

        self.nn_component = None  # type: depthai_sdk.components.NNComponent
        self.callback = None

    def set_callback(self, callback: Callable) -> None:
        self.callback = callback
