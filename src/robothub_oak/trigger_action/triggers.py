from datetime import timedelta
from typing import Union, Callable, Dict

from robothub_oak.components import Stereo, NeuralNetwork, Camera
from robothub_oak.packets import HubPacket

__all__ = ['Trigger', 'DetectionTrigger']


class Trigger:
    """
    Generic trigger class. Can be used to create custom triggers via providing a condition function.
    """

    def __init__(self,
                 component: Union[Camera, Stereo, NeuralNetwork],
                 condition: Callable[[HubPacket], bool],
                 cooldown: int = 30):
        self.component = component
        self.condition = condition
        self.cooldown = cooldown


class DetectionTrigger:
    def __init__(self,
                 input: NeuralNetwork,
                 min_detections: Dict[str, int],
                 cooldown: Union[timedelta, int]):
        self.input = input
        self.min_detections = min_detections
        self.cooldown = cooldown
