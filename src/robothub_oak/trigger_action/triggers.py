from typing import Union, Callable

from robothub_oak.components import Stereo, NeuralNetwork, Camera

__all__ = ['Trigger']


class Trigger:
    def __init__(self,
                 component: Union[Camera, Stereo, NeuralNetwork],
                 condition: Callable,
                 cooldown: int = 30):
        self.component = component
        self.condition = condition
        self.cooldown = cooldown
