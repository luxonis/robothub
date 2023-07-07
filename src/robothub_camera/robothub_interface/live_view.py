import time

from robothub import STREAMS
from typing import List, Optional


BoundingBox: tuple[int, int, int, int]


def _create_stream_handle(camera_serial: str, unique_key: str, title: str):
    if title not in STREAMS.streams:
        color_stream_handle = STREAMS.create_video(camera_serial, title, title)
    else:
        color_stream_handle = STREAMS.streams[unique_key]
    return color_stream_handle


def _publish_stream(stream_handle, rectangles: List[BoundingBox], rectangle_labels: List[str], texts: list[str], h264_encoded, frame_width: int, frame_height: int):
    """TBD
    """

    timestamp = int(time.time() * 1_000)
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
        metadata["objects"][0]["detections"].append({'bbox': [xmin, ymin, xmax, ymax], 'label': label, 'color': [0, 255, 255]})
    for idx, text in enumerate(texts):
        x_coordinate = idx * frame_width // len(texts) + 30  # plus offset
        metadata["objects"].append({'type': "text", 'coords': [x_coordinate, 40], "text": text})
    stream_handle.publish_video_data(bytes(h264_encoded), timestamp, metadata)


class LiveView:

    LIVE_VIEWS: dict[str, 'LiveView'] = dict()

    def __init__(self, frame_width: int, frame_height: int, camera_serial: str, unique_key: str, title: str):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.camera_serial = camera_serial
        self.unique_key = unique_key
        self.title = title

        # text display
        self.exposure = 0
        self.iso = 0
        self.focus = 0
        self.direction_of_travel = "None"

        self.stream_handle = _create_stream_handle(camera_serial=camera_serial, unique_key=unique_key, title=title)
        self.rectangles: List[BoundingBox] = []
        self.labels: List[str] = []

    @staticmethod
    def get_live_view(name: str) -> Optional['LiveView']:
        return LiveView.LIVE_VIEWS.get(name)

    def draw_rectangle(self, rectangle: BoundingBox, label: str) -> None:
        self.rectangles.append(rectangle)
        self.labels.append(label)

    def _publish(self, h264_frame) -> None:
        texts = [f"Exposure: {self.exposure}", f"ISO: {self.iso}", f"Focus: {self.focus}", f"DoT: {self.direction_of_travel}"]
        _publish_stream(stream_handle=self.stream_handle, rectangles=self.rectangles, rectangle_labels=self.labels, texts=texts, h264_encoded=h264_frame, frame_width=self.frame_width, frame_height=self.frame_height)

    def h264_callback(self, h264_packet):
        self._publish(h264_frame=h264_packet)
        self._reset_overlays()

    def _reset_overlays(self):
        self.rectangles = []
        self.labels = []
