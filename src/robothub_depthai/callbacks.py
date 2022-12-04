import time
from functools import partial

from depthai_sdk.callback_context import CallbackContext
from robothub import StreamHandle


def default_color_callback(stream_handle: StreamHandle, ctx: CallbackContext):
    packet = ctx.packet

    timestamp = int(time.time() * 1_000)
    frame_bytes = bytes(packet.imgFrame.getData())
    stream_handle.publish_video_data(frame_bytes, timestamp, None)


def get_default_color_callback(stream_handle: StreamHandle):
    return partial(default_color_callback, stream_handle)

# TODO callbacks for NN, stereo, etc
