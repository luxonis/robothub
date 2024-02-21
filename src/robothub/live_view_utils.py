import logging

import numpy as np
try:
    import robothub_core
except ImportError:
    import robothub.robothub_core_wrapper as robothub_core

__all__ = [
    'is_h264_frame',
    'create_stream_handle'
]

logger = logging.getLogger(__name__)


def is_h264_frame(data):
    """
    Check if the given data (numpy array) starts with an H.264 NAL unit.
    This function checks for the presence of H.264 start codes and NAL types.
    """
    if len(data) < 4:
        return False

    # Check for the start code in the numpy array
    if np.array_equal(data[:3], np.array([0x00, 0x00, 0x01])):
        nal_unit_type = data[3] & 0x1F
    elif np.array_equal(data[:4], np.array([0x00, 0x00, 0x00, 0x01])):
        nal_unit_type = data[4] & 0x1F
    else:
        return False

    # Check if NAL unit type is in the valid range (0-31)
    return 0 < nal_unit_type <= 31


def create_stream_handle(camera_serial: str, unique_key: str, name: str):
    """
    Create or get existing stream handle.

    :param camera_serial: Device MXID.
    :param unique_key: Unique key for the stream.
    :param name: Name of the stream.
    :return: robothub_core.StreamHandle object.
    """
    if unique_key not in robothub_core.STREAMS.streams:
        color_stream_handle = robothub_core.STREAMS.create_video(camera_serial, unique_key, name)
    else:
        color_stream_handle = robothub_core.STREAMS.streams[unique_key]
    return color_stream_handle
