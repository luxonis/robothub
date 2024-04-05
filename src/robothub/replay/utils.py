from datetime import timedelta

import cv2
import depthai as dai
import numpy as np


# from https://github.com/opencv/opencv/issues/21727#issuecomment-1068908078
def BGR2YUV_NV12(src):
    src_h, src_w = src.shape[:2]
    # Convert BGR to YUV_I420
    dst = cv2.cvtColor(src, cv2.COLOR_BGR2YUV_I420)
    n_y = src_h * src_w
    n_uv = n_y // 2
    n_u = n_y // 4

    # Extract the Y plane
    y_plane = dst[:src_h].reshape((src_h, src_w))

    # Extract the U and V planes, then interleave them for NV12 format
    u_plane = dst[src_h : src_h + src_h // 4].reshape((-1, src_w // 2))
    v_plane = dst[src_h + src_h // 4 :].reshape((-1, src_w // 2))

    uv_plane = np.zeros((src_h // 2, src_w), dtype=np.uint8)
    uv_plane[:, 0::2] = u_plane.reshape((-1, src_w // 2))
    uv_plane[:, 1::2] = v_plane.reshape((-1, src_w // 2))

    # Combine Y and interleaved UV planes into one NV12 image
    nv12_img = np.vstack((y_plane, uv_plane)).astype(np.uint8)
    return nv12_img


def to_planar(arr: np.ndarray, shape: tuple) -> np.ndarray:
    return cv2.resize(arr, shape).transpose(2, 0, 1).flatten()


def create_img_frame(
    data: np.ndarray,
    width: int,
    height: int,
    type: dai.RawImgFrame.Type,
    sequence_number: int,
    timestamp: timedelta,
    camera_socket: dai.CameraBoardSocket | None = None,
):
    img_frame = dai.ImgFrame()
    img_frame.setType(type)
    img_frame.setData(data.flatten())
    img_frame.setTimestamp(timestamp)
    img_frame.setSequenceNum(sequence_number)
    img_frame.setWidth(width)
    img_frame.setHeight(height)
    if camera_socket is not None:
        img_frame.setInstanceNum(int(camera_socket))
    return img_frame
