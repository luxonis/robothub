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


def get_default_color_callback(stream_handle: StreamHandle, visualizer_callback: Callable = None) -> Callable:
    """
    Returns a default callback for color streams.

    :param stream_handle: StreamHandle instance to publish the data to.
    :param visualizer_callback: Callback that will be called inside the default callback.
    """
    return partial(_default_encoded_callback, stream_handle, visualizer_callback)


def get_default_nn_callback(stream_handle: StreamHandle, visualizer_callback: Callable = None) -> Callable:
    """
    Returns a default callback for NN streams.

    :param stream_handle: StreamHandle instance to publish the data to.
    :param visualizer_callback: Callback that will be called inside the default callback.
    """
    return partial(_default_nn_callback, stream_handle, visualizer_callback)


def get_default_depth_callback(stream_handle: StreamHandle, visualizer_callback: Callable = None) -> Callable:
    """
    Returns a default callback for depth streams.

    :param stream_handle: StreamHandle instance to publish the data to.
    :param visualizer_callback: Callback that will be called inside the default callback.
    """
    return partial(_default_encoded_callback, stream_handle, visualizer_callback)


def _default_encoded_callback(stream_handle: StreamHandle, packet):
    """
    Default callback for encoded streams.

    :param stream_handle: StreamHandle instance to publish the data to.
    :param packet: Packet instance containing the data.
    """

    timestamp = int(time.perf_counter_ns() / 1_000_000)
    frame_bytes = bytes(packet.msg.getData())
    stream_handle.publish_video_data(frame_bytes, timestamp, None)


def _default_nn_callback(stream_handle: StreamHandle, visualizer_callback, packet):
    """
    Default callback for NN streams.

    :param stream_handle: StreamHandle instance to publish the data to.
    :param visualizer_callback: Callback that will be called inside this callback.
    :param packet: Packet instance containing the data.
    """
    if visualizer_callback:  # Call the user's callback
        visualizer_callback(packet)

    # Get the metadata from the packet
    visualizer = packet.visualizer
    metadata = json.loads(visualizer.serialize()) if visualizer else None

    timestamp = int(time.perf_counter_ns() / 1_000_000)
    frame_bytes = bytes(packet.msg.getData())
    stream_handle.publish_video_data(frame_bytes, timestamp, metadata)
