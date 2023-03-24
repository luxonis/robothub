from typing import Union, Callable, Optional

from robothub_oak.components import Camera
from robothub_oak.components.streamable import Streamable

__all__ = ['NeuralNetwork']


class NeuralNetwork(Streamable):
    def __init__(self,
                 name: str,
                 input: Union[Camera, 'NeuralNetwork'],
                 nn_type: Optional[str] = None,  # Either 'yolo' or 'mobilenet'
                 decode_fn: Optional[Callable] = None,
                 tracker: bool = False,
                 spatial: Optional[bool] = None):
        super().__init__()
        self.name = name
        self.input = input
        self.nn_type = nn_type
        self.decode_fn = decode_fn
        self.tracker = tracker
        self.spatial = spatial

        self.nn_component = None  # type: depthai_sdk.components.NNComponent
        self.callbacks = []

    def add_callback(self, callback: Callable) -> None:
        self.callbacks.append(callback)

    def configure(self, **kwargs) -> None:
        pass
