import time
from typing import List, Optional, Union, Dict, Tuple

import depthai as dai
import numpy as np
import robothub_core
from depthai_sdk import OakCamera
from depthai_sdk.components import Component, CameraComponent, StereoComponent, NNComponent
from depthai_sdk.oak_outputs.xout.xout_base import StreamXout
from depthai_sdk.oak_outputs.xout.xout_h26x import XoutH26x
from depthai_sdk.visualize.objects import VisText, VisLine

from robothub.types import BoundingBox

__all__ = ['LiveView', 'LIVE_VIEWS']


def _create_stream_handle(camera_serial: str, unique_key: str, name: str):
    if unique_key not in robothub_core.STREAMS.streams:
        color_stream_handle = robothub_core.STREAMS.create_video(camera_serial, unique_key, name)
    else:
        color_stream_handle = robothub_core.STREAMS.streams[unique_key]
    return color_stream_handle


def _publish_data(stream_handle: robothub_core.StreamHandle,
                  h264_frame,
                  rectangles: List[BoundingBox],
                  rectangle_labels: List[str],
                  texts: List[VisText],
                  lines: List[VisLine],
                  frame_width: int,
                  frame_height: int):
    timestamp = int(time.perf_counter_ns() / 1e6)
    metadata = {
        "platform": "robothub",
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

    # Bounding boxes
    for roi, label in zip(rectangles, rectangle_labels):
        xmin, ymin, xmax, ymax = roi
        metadata['objects'][0]['detections'].append(
            {'bbox': [xmin, ymin, xmax, ymax], 'label': label, 'color': [0, 255, 255]}
        )

    # Texts
    for text in texts:
        metadata["objects"].append(text.prepare().serialize())

    # Lines
    for line in lines:
        metadata["objects"].append(line.prepare().serialize())

    # Publish
    stream_handle.publish_video_data(bytes(h264_frame), timestamp, metadata)


class LiveView:
    def __init__(self,
                 name: str,
                 unique_key: str,
                 device_mxid: str,
                 frame_width: int,
                 frame_height: int):
        """
        :param name: Name of the Live View.
        :param unique_key: Live View identifier.
        :param device_mxid: MXID of the device that is streaming the Live View.
        :param frame_width: Frame width.
        :param frame_height: Frame height.
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.device_mxid = device_mxid
        self.unique_key = unique_key
        self.name = name

        self.stream_handle = _create_stream_handle(camera_serial=device_mxid, unique_key=unique_key, name=name)

        # Objects
        self.texts: List[VisText] = []
        self.rectangles: List[BoundingBox] = []
        self.labels: List[str] = []
        self.lines: List[VisLine] = []

    @staticmethod
    def create(device: OakCamera,
               component: Union[CameraComponent, StereoComponent],
               name: str,
               unique_key: str = None,
               manual_publish: bool = False
               ) -> 'LiveView':
        """
        Creates a Live View for a given component.

        :param device: OakCamera instance.
        :param component: Component to create a Live View for. Either a CameraComponent, StereoComponent or NNComponent.
        :param name: Name of the Live View.
        :param unique_key: Live View identifier.
        :param manual_publish: If True, the Live View will not be automatically published. Use LiveView.publish() to publish the Live View.
        """
        output = None
        is_h264 = LiveView.is_encoder_enabled(component)
        if not is_h264:
            output = LiveView.h264_output(device, component)
        elif not is_h264 and not isinstance(component, CameraComponent):
            raise ValueError(f'Component {component.__class__.__name__} must have h264 encoding '
                             f'enabled to be used with LiveView.')

        w, h = LiveView.get_stream_size(component)
        device_mxid = device.device.getMxId()
        unique_key = unique_key or f'{device_mxid}_{component.__class__.__name__.lower()}_encoded'

        live_view = LiveView(name=name,
                             unique_key=unique_key,
                             device_mxid=device_mxid,
                             frame_width=w,
                             frame_height=h)

        if not manual_publish:
            device.callback(output or component.out.encoded, live_view.h264_callback)

        LIVE_VIEWS[unique_key] = live_view
        return live_view

    @staticmethod
    def h264_output(device: OakCamera, component: CameraComponent):
        fps = 30
        if isinstance(component, StereoComponent):
            fps = component._fps
        elif isinstance(component, CameraComponent):
            fps = component.get_fps()

        encoder = device.pipeline.createVideoEncoder()
        encoder_profile = dai.VideoEncoderProperties.Profile.H264_MAIN
        encoder.setDefaultProfilePreset(fps, encoder_profile)
        encoder.input.setQueueSize(1)
        encoder.input.setBlocking(False)
        encoder.setKeyframeFrequency(int(fps))
        encoder.setBitrate(1500 * 1000)
        encoder.setRateControlMode(dai.VideoEncoderProperties.RateControlMode.CBR)
        encoder.setNumFramesPool(3)

        component.node.video.link(encoder.input)

        def encoded(pipeline, device):
            xout = XoutH26x(
                frames=StreamXout(encoder.id, encoder.bitstream),
                color=True,
                profile=encoder_profile,
                fps=encoder.getFrameRate(),
                frame_shape=component.node.getResolution()
            )
            xout.name = component._source
            return component._create_xout(pipeline, xout)

        return encoded

    @staticmethod
    def is_encoder_enabled(component: Component) -> bool:
        """
        Checks if the component has h264 encoding enabled.

        :param component: Component to check.
        :return: True if the component has h264 encoding enabled, False otherwise.
        :raises ValueError: If the component is not a CameraComponent or StereoComponent.
        """
        if not isinstance(component, CameraComponent) and not isinstance(component, StereoComponent):
            raise ValueError(f'Component {component.__class__.__name__} must be a CameraComponent or StereoComponent.')
        encoder = component.encoder

        if encoder and encoder.getProfile() != dai.VideoEncoderProperties.Profile.H264_MAIN:
            return False

        return True

    @staticmethod
    def get_stream_size(component) -> Tuple[int, int]:
        if isinstance(component, CameraComponent):
            return component.stream_size
        elif isinstance(component, StereoComponent):
            return component.left.stream_size
        elif isinstance(component, NNComponent):
            return component._input.stream_size

    @staticmethod
    def get(unique_key: str = None, name: str = None):
        if name is not None:
            return LiveView.get_by_name(name)
        elif unique_key is not None:
            return LiveView.get_by_unique_key(unique_key)
        else:
            raise ValueError('Either name or unique_key must be specified.')

    @staticmethod
    def get_by_name(name: str) -> Optional['LiveView']:
        for live_view in LIVE_VIEWS.values():
            if live_view.name == name:
                return live_view
        return None

    @staticmethod
    def get_by_unique_key(unique_key: str) -> Optional['LiveView']:
        if unique_key not in LIVE_VIEWS:
            raise ValueError(f'Live View with unique_key {unique_key} does not exist.')

        return LIVE_VIEWS[unique_key]

    def add_rectangle(self, rectangle: BoundingBox, label: str) -> None:
        self.rectangles.append(rectangle)
        self.labels.append(label)

    def add_text(self,
                 text: str,
                 coords: Tuple[int, int],
                 size: int = None,
                 color: Tuple[int, int, int] = None,
                 thickness: int = None,
                 outline: bool = True,
                 background_color: Tuple[int, int, int] = None,
                 background_transparency: float = 0.5) -> None:
        obj = VisText(text, coords, size, color, thickness, outline, background_color, background_transparency)
        self.texts.append(obj)

    def add_line(self,
                 pt1: Tuple[int, int],
                 pt2: Tuple[int, int],
                 color: Tuple[int, int, int] = None,
                 thickness: int = None
                 ) -> None:
        obj = VisLine(pt1, pt2, color, thickness)
        self.lines.append(obj)

    def publish(self, h264_frame: Union[np.array, List]) -> None:
        _publish_data(stream_handle=self.stream_handle,
                      h264_frame=h264_frame,
                      rectangles=self.rectangles,
                      rectangle_labels=self.labels,
                      texts=self.texts,
                      lines=self.lines,
                      frame_width=self.frame_width,
                      frame_height=self.frame_height)
        self._reset_overlays()

    def h264_callback(self, h264_packet):
        self.publish(h264_frame=h264_packet.frame)

    def _reset_overlays(self):
        self.rectangles.clear()
        self.labels.clear()
        self.lines.clear()
        self.texts.clear()


LIVE_VIEWS: Dict[str, LiveView] = dict()
