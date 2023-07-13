import time
from typing import List, Optional, Union, Dict

import depthai as dai
import numpy as np
import robothub_core
from depthai_sdk import OakCamera
from depthai_sdk.components import Component, CameraComponent, StereoComponent, NNComponent

from robothub.types import BoundingBox, Line

__all__ = ['LiveView', 'LIVE_VIEWS']


def _create_stream_handle(camera_serial: str, unique_key: str, title: str):
    if title not in robothub_core.STREAMS.streams:
        color_stream_handle = robothub_core.STREAMS.create_video(camera_serial, title, title)
    else:
        color_stream_handle = robothub_core.STREAMS.streams[unique_key]
    return color_stream_handle


def _publish_data(stream_handle: robothub_core.StreamHandle,
                  rectangles: List[BoundingBox],
                  rectangle_labels: List[str],
                  texts: List[str],
                  h264_encoded,
                  frame_width: int,
                  frame_height: int):
    timestamp = int(time.perf_counter_ns() / 1e6)
    metadata = {
        "platform": "robothub_core",
        "frame_shape": [frame_height, frame_width],
        "config": {
            "output": {
                "img_scale": 1.0,
                "show_fps": False,
                "clickable": True
            },
            "detection": {
                "thickness": 1,
                "fill_transparency": 0.05,
                "box_roundness": 0,
                "color": [0, 255, 0],
                "bbox_style": 0,
                "line_width": 0.5,
                "line_height": 0.5,
                "hide_label": False,
                "label_position": 0,
                "label_padding": 10
            },
            'text': {
                'font_color': [255, 255, 0],
                'font_transparency': 0.5,
                'font_scale': 1.0,
                'font_thickness': 2,
                'bg_transparency': 0.5,
                'bg_color': [0, 0, 0]
            }
        },
        "objects": [
            {
                "type": "detections",
                "detections": []
            }
        ]
    }

    for roi, label in zip(rectangles, rectangle_labels):
        xmin, ymin, xmax, ymax = roi
        metadata['objects'][0]['detections'].append(
            {'bbox': [xmin, ymin, xmax, ymax], 'label': label, 'color': [0, 255, 255]}
        )

    for idx, text in enumerate(texts):
        x_coordinate = idx * frame_width // len(texts) + 30  # plus offset
        metadata["objects"].append({'type': 'text', 'coords': [x_coordinate, 40], 'text': text})

    stream_handle.publish_video_data(bytes(h264_encoded), timestamp, metadata)


class LiveView:
    def __init__(self,
                 title: str,
                 unique_key: str,
                 device_mxid: str,
                 frame_width: int,
                 frame_height: int):
        """
        :param title: Name of the Live View.
        :param unique_key: Live View identifier.
        :param device_mxid: MXID of the device that is streaming the Live View.
        :param frame_width: Frame width.
        :param frame_height: Frame height.
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.device_mxid = device_mxid
        self.unique_key = unique_key
        self.title = title

        self.stream_handle = _create_stream_handle(camera_serial=device_mxid, unique_key=unique_key, title=title)

        # Objects
        self.texts: List[str] = []
        self.rectangles: List[BoundingBox] = []
        self.labels: List[str] = []
        self.lines: List[Line] = []

        self.live_views = {}

    @staticmethod
    def create(oak: OakCamera, component: Component, title: str) -> None:
        """Creates a Live View for a component."""
        LiveView.verify_encoder_profile(component)

        live_view = LiveView(title=title,
                             unique_key="some_key",
                             device_mxid=oak.device.getMxId(),
                             frame_width=1920,
                             frame_height=1080)

        oak.callback(component.out.encoded, live_view.h264_callback)
        LIVE_VIEWS[title] = live_view

    @staticmethod
    def verify_encoder_profile(component: Component) -> None:
        encoder = None
        if isinstance(component, CameraComponent) or isinstance(component, StereoComponent):
            encoder = component.encoder
        elif isinstance(component, NNComponent):
            encoder = component._input.encoder
        if encoder.getProfile() != dai.VideoEncoderProperties.Profile.H264_MAIN:
            raise ValueError('Live View component must be configured with H264 encoding.')

    @staticmethod
    def get_by_name(name: str) -> Optional['LiveView']:
        return LIVE_VIEWS.get(name, None)

    def add_rectangle(self, rectangle: BoundingBox, label: str) -> None:
        self.rectangles.append(rectangle)
        self.labels.append(label)

    def add_bbox(self, bbox: BoundingBox, label: str) -> None:
        self.add_rectangle(bbox, label)

    # TODO: add_line, add_text
    def add_text(self, text: str) -> None:
        pass

    def add_line(self, line: BoundingBox, label: str) -> None:
        pass

    def publish(self, h264_frame: Union[np.array, List]) -> None:
        _publish_data(stream_handle=self.stream_handle,
                      rectangles=self.rectangles,
                      rectangle_labels=self.labels,
                      h264_encoded=h264_frame,
                      texts=[],
                      frame_width=self.frame_width,
                      frame_height=self.frame_height)

    def h264_callback(self, h264_packet):
        self.publish(h264_frame=h264_packet)
        self._reset_overlays()

    def _reset_overlays(self):
        self.rectangles = []
        self.labels = []


LIVE_VIEWS: Dict[str, LiveView] = dict()