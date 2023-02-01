import json
import time
from functools import partial
from typing import Callable

from robothub import StreamHandle

__all__ = [
    'get_default_color_callback',
    'get_default_nn_callback',
    'get_default_depth_callback',
]


def get_default_color_callback(stream_handle: StreamHandle) -> Callable:
    """
    Returns a default callback for color streams.

    :param stream_handle: StreamHandle instance to publish the data to.
    """
    return partial(_default_encoded_callback, stream_handle)


def get_default_nn_callback(stream_handle: StreamHandle) -> Callable:
    """
    Returns a default callback for NN streams.

    :param stream_handle: StreamHandle instance to publish the data to.
    """
    return partial(_default_nn_callback, stream_handle)


def get_default_depth_callback(stream_handle: StreamHandle) -> Callable:
    """
    Returns a default callback for depth streams.

    :param stream_handle: StreamHandle instance to publish the data to.
    """
    return partial(_default_encoded_callback, stream_handle)


def _default_encoded_callback(stream_handle: StreamHandle, packet):
    """
    Default callback for encoded streams.

    :param stream_handle: StreamHandle instance to publish the data to.
    :param packet: Packet instance containing the data.
    """

    timestamp = int(time.time() * 1_000)
    frame_bytes = bytes(packet.imgFrame.getData())
    stream_handle.publish_video_data(frame_bytes, timestamp, None)


def _default_nn_callback(stream_handle: StreamHandle, packet):
    """
    Default callback for NN streams.

    :param stream_handle: StreamHandle instance to publish the data to.
    :param packet: Packet instance containing the data.
    """
    visualizer = packet.visualizer
    metadata = None
    if visualizer:
        metadata = json.loads(visualizer.serialize())
        visualizer.reset()

        # temp fix to replace None value that causes errors on frontend
        if not metadata['config']['detection']['color']:
            metadata['config']['detection']['color'] = [255, 0, 0]

    timestamp = int(time.time() * 1_000)
    frame_bytes = bytes(packet.imgFrame.getData())
    stream_handle.publish_video_data(frame_bytes, timestamp, metadata)
