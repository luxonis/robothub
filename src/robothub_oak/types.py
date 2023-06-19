from typing import Union

from robothub_oak.components import Camera, Stereo, NeuralNetwork

Component = Union[Camera, NeuralNetwork, Stereo]
