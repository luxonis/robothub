from dataclasses import dataclass, replace
from typing import Union, Callable, Optional, List

import depthai as dai
import depthai_sdk
import depthai_sdk.components

from robothub_oak.components import Camera
from robothub_oak.components._component import Component
from robothub_oak.components.streamable import Streamable
from robothub_oak.utils import _process_kwargs, _get_methods_by_class

__all__ = ['NeuralNetwork']


@dataclass
class NNConfig:
    resize_mode: Optional[depthai_sdk.ResizeMode] = None
    conf_threshold: Optional[float] = None


@dataclass
class TrackerConfig:
    tracker_type: Optional[dai.TrackerType] = None
    track_labels: Optional[List[int]] = None
    assignment_policy: Optional[dai.TrackerIdAssignmentPolicy] = None
    max_obj: Optional[int] = None
    threshold: Optional[float] = None
    apply_tracking_filter: Optional[bool] = None
    forget_after_n_frames: Optional[int] = None
    calculate_speed: Optional[bool] = None


class NeuralNetwork(Component, Streamable):
    def __init__(self,
                 name: str,
                 input: Union[Camera, 'NeuralNetwork'],
                 nn_type: Optional[str] = None,  # Either 'yolo' or 'mobilenet'
                 decode_fn: Optional[Callable] = None,
                 tracker: bool = False,
                 spatial: Optional[bool] = None):
        Component.__init__(self)
        Streamable.__init__(self)
        self.name = name
        self.input = input
        self.nn_type = nn_type
        self.decode_fn = decode_fn
        self.tracker = tracker
        self.spatial = spatial

        self.nn_config = NNConfig()
        self.tracker_config = TrackerConfig()

        self.nn_component: Optional[depthai_sdk.components.NNComponent] = None

    def configure(self,
                  conf_threshold: Optional[float] = None,
                  resize_mode: depthai_sdk.ResizeMode = None,
                  ) -> None:
        if conf_threshold is not None:
            self.nn_config.conf_threshold = conf_threshold
        if resize_mode is not None:
            self.nn_config.resize_mode = resize_mode

    def configure_tracker(self,
                          tracker_type: Optional[dai.TrackerType] = None,
                          track_labels: Optional[List[int]] = None,
                          assignment_policy: Optional[dai.TrackerIdAssignmentPolicy] = None,
                          max_obj: Optional[int] = None,
                          threshold: Optional[float] = None,
                          apply_tracking_filter: Optional[bool] = None,
                          forget_after_n_frames: Optional[int] = None,
                          calculate_speed: Optional[bool] = None
                          ) -> None:
        kwargs = _process_kwargs(locals())

        if len(kwargs) > 0:
            self.tracker_config = replace(self.tracker_config, **kwargs)

    def set_valid_output_types(self) -> None:
        self._valid_output_types = _get_methods_by_class(depthai_sdk.components.NNComponent.Out)
