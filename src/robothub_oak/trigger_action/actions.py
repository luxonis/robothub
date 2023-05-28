from datetime import timedelta
from typing import Callable, Union, List, Any

from robothub_oak.types import Component

__all__ = ['Action', 'RecordAction']


class Action:
    def __init__(self, inputs: Union[Component, List[Component]] = None, action: Callable = None):
        self.inputs = inputs
        self.action = action


class RecordAction(Action):
    def __init__(self,
                 inputs: Union[Component, Callable, List[Union[Component, Callable]]],
                 dir_path: str,
                 duration_before_trigger: Union[int, timedelta],
                 duration_after_trigger: Union[timedelta, int],
                 upload_to_hub: bool = True):
        super().__init__(inputs=inputs)

        self.dir_path = dir_path
        self.duration_before_trigger = duration_before_trigger
        self.duration_after_trigger = duration_after_trigger
        self.upload_to_hub = upload_to_hub
