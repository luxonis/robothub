from typing import Union, Optional, List, Dict

import depthai as dai
import depthai_sdk


class NNComponent:
    def __init__(self, component: depthai_sdk.components.NNComponent):
        self.component = component

        # Tracker
        self.tracker_type = None
        self.track_labels = None
        self.assignment_policy = None
        self.max_obj = None
        self.threshold = None
        # NN
        self.conf_threshold = None
        self.resize_mode = None
        # Spatial
        self.bb_scale_factor = None
        self.lower_threshold = None
        self.upper_threshold = None
        self.calc_algo = None
        # Yolo
        self.num_classes = None
        self.coordinate_size = None
        self.anchors = None
        self.masks = None
        self.iou_threshold = None
        self.conf_threshold_yolo = None

    def apply_config_from_component(self, component: 'NNComponent'):
        """
        Applies configuration from another CameraComponent instance. Used after reconnecting the device.
        """
        self.config_tracker(component.tracker_type, component.track_labels, component.assignment_policy,
                            component.max_obj, component.threshold)
        self.config_nn(component.conf_threshold, component.resize_mode)
        self.config_spatial(component.bb_scale_factor, component.lower_threshold,
                            component.upper_threshold, component.calc_algo)
        self.config_yolo(component.num_classes, component.coordinate_size, component.anchors,
                         component.masks, component.iou_threshold, component.conf_threshold_yolo)

    def config_tracker(self,
                       tracker_type: Optional[dai.TrackerType] = None,
                       track_labels: Optional[List[int]] = None,
                       assignment_policy: Optional[dai.TrackerIdAssignmentPolicy] = None,
                       max_obj: Optional[int] = None,
                       threshold: Optional[float] = None):
        self.component.config_tracker(tracker_type, track_labels, assignment_policy, max_obj, threshold)

        self.tracker_type = tracker_type
        self.track_labels = track_labels
        self.assignment_policy = assignment_policy
        self.max_obj = max_obj
        self.threshold = threshold

    def config_nn(self,
                  conf_threshold: Optional[float] = None,
                  resize_mode: Union[depthai_sdk.ResizeMode, str] = None):
        self.component.config_nn(conf_threshold, resize_mode)

        self.conf_threshold = conf_threshold
        self.resize_mode = resize_mode

    def config_spatial(self,
                       bb_scale_factor: Optional[float] = None,
                       lower_threshold: Optional[int] = None,
                       upper_threshold: Optional[int] = None,
                       calc_algo: Optional[dai.SpatialLocationCalculatorAlgorithm] = None):
        self.component.config_spatial(bb_scale_factor, lower_threshold, upper_threshold, calc_algo)

        self.bb_scale_factor = bb_scale_factor
        self.lower_threshold = lower_threshold
        self.upper_threshold = upper_threshold
        self.calc_algo = calc_algo

    def config_yolo(self,
                    num_classes: int,
                    coordinate_size: int,
                    anchors: List[float],
                    masks: Dict[str, List[int]],
                    iou_threshold: float,
                    conf_threshold: Optional[float] = None):
        self.component.config_yolo(num_classes, coordinate_size, anchors, masks, iou_threshold, conf_threshold)

        self.num_classes = num_classes
        self.coordinate_size = coordinate_size
        self.anchors = anchors
        self.masks = masks
        self.iou_threshold = iou_threshold
        self.conf_threshold_yolo = conf_threshold

    @property
    def out(self):
        return self.component.out
