import json
import time
from functools import partial
from typing import Callable

from depthai_sdk.callback_context import CallbackContext
from robothub import StreamHandle

__all__ = [
    'get_default_color_callback',
    'get_default_nn_callback',
    'get_default_depth_callback',
]


def get_default_color_callback(stream_handle: StreamHandle) -> Callable[[CallbackContext], None]:
    """
    Returns a default callback for color streams.

    :param stream_handle: StreamHandle instance to publish the data to.
    """
    return partial(_default_encoded_callback, stream_handle)


def get_default_nn_callback(stream_handle: StreamHandle) -> Callable[[CallbackContext], None]:
    """
    Returns a default callback for NN streams.

    :param stream_handle: StreamHandle instance to publish the data to.
    """
    return partial(_default_nn_callback, stream_handle)


def get_default_depth_callback(stream_handle: StreamHandle) -> Callable[[CallbackContext], None]:
    """
    Returns a default callback for depth streams.

    :param stream_handle: StreamHandle instance to publish the data to.
    """
    return partial(_default_encoded_callback, stream_handle)


def _default_encoded_callback(stream_handle: StreamHandle, ctx: CallbackContext):
    """
    Default callback for encoded streams.

    :param stream_handle: StreamHandle instance to publish the data to.
    :param ctx: CallbackContext instance containing e.g. the packet and visualizer.
    """
    packet = ctx.packet

    timestamp = int(time.time() * 1_000)
    frame_bytes = bytes(packet.imgFrame.getData())
    stream_handle.publish_video_data(frame_bytes, timestamp, None)


def _default_nn_callback(stream_handle: StreamHandle, ctx: CallbackContext):
    """
    Default callback for NN streams.

    :param stream_handle: StreamHandle instance to publish the data to.
    :param ctx: CallbackContext instance containing e.g. the packet and visualizer.
    """
    packet = ctx.packet
    visualizer = ctx.visualizer

    metadata = json.loads(visualizer.serialize())
    visualizer.reset()

    # temp fix to replace None value that causes errors on frontend
    if not metadata['config']['detection']['color']:
        metadata['config']['detection']['color'] = [255, 0, 0]

    timestamp = int(time.time() * 1_000)
    frame_bytes = bytes(packet.imgFrame.getData())
    stream_handle.publish_video_data(frame_bytes, timestamp, metadata)
