import logging
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Union

import cv2
import numpy as np

try:
    import robothub_core
except ImportError:
    import robothub.robothub_core_wrapper as robothub_core

__all__ = ['send_image_event', 'send_frame_event_with_zipped_images', 'send_video_event', 'FutureEvent', 'UploadedEvent']

logger = logging.getLogger(__name__)

FutureEvent = robothub_core.events.FutureEvent
UploadedEvent = robothub_core.events.UploadedEvent


def _catch_event_exception(func):
    """
    Catch exceptions when sending events to RH.
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f'Failed to send event: {e}')
            _log_event_status(False, "None")
            return None

    return wrapper


def _log_event_status(result: bool, event_id):
    if result:
        logger.info(f"Event {event_id}: sent successfully.")
    else:
        logger.info(f'Event {event_id}: failed to send.')


@_catch_event_exception
def send_image_event(image: Union[np.ndarray, bytes],
                     title: str,
                     device_id: str = None,
                     metadata: Optional[dict] = None,
                     tags: List[str] = None,
                     mjpeg_quality=98,
                     encode=False
                     ) -> Optional[str]:
    """
    Send a single image frame event to RH.

    :param image: The image to send.
    :param title: The title of the event.
    :param device_id: The device ID to associate with the event.
    :param metadata: A dictionary of metadata to associate with the event.
    :param tags: A list of tags to associate with the event.
    :param mjpeg_quality: The JPEG quality to use when encoding.
    :param encode: Whether to encode the image as a JPEG before sending.
    :return: The event ID. None if the event failed to send.
    """
    if encode:
        _, image = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), mjpeg_quality])

    event = robothub_core.EVENTS.prepare()
    event.add_frame(bytes(image), device_id)
    event.set_title(title)
    if metadata:
        event.set_metadata(metadata)
    if tags:
        event.add_tags(tags)
    robothub_core.EVENTS.upload(event)
    _log_event_status(True, event.id)
    return event.id


@_catch_event_exception
def send_frame_event_with_zipped_images(cv_frame: np.ndarray,
                                        files: list,
                                        title: str,
                                        device_id: str,
                                        tags: List[str] = None,
                                        metadata: Optional[dict] = None,
                                        encode: bool = False,
                                        mjpeg_quality=98
                                        ) -> Optional[str]:
    """
    Send a collection of images as a single event to RH.

    :param cv_frame: The main image frame to send.
    :param files: A list of images to zip and send.
    :param title: The title of the event.
    :param device_id: The device ID to associate with the event.
    :param tags: A list of tags to associate with the event.
    :param metadata: A dictionary of metadata to associate with the event.
    :param encode: Whether to encode the images as JPEGs before sending.
    :param mjpeg_quality: The JPEG quality to use when encoding.
    :return: The event ID. None if the event failed to send.
    """
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), mjpeg_quality]
    if encode:
        _, cv_frame = cv2.imencode('.jpg', cv_frame, encode_param)

    event = robothub_core.EVENTS.prepare()
    event.add_frame(bytes(cv_frame), device_id)
    event.set_title(title)
    if tags:
        event.set_tags(tags)
    if metadata:
        event.set_metadata(metadata)
    logger.debug(f'Total files: {len(files)}')
    with BytesIO() as zip_buffer:
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for idx, file in enumerate(files):
                if encode:
                    _, encoded = cv2.imencode('.jpg', file, encode_param)
                else:
                    encoded = file
                # Convert the numpy array to bytes
                image_bytes = encoded.tobytes()
                # Add the bytes to the zip file with a unique filename
                filename = f'image_{idx}.jpeg'
                zip_file.writestr(filename, image_bytes)
                # event.add_file(bytes(encoded), name=f"image_{idx}.jpeg")
        # Get the bytes of the zip file
        zip_bytes = zip_buffer.getvalue()
        event.add_file(zip_bytes, name=f'images.zip')
        robothub_core.EVENTS.upload(event)
        _log_event_status(True, event.id)
        return event.id


@_catch_event_exception
def send_video_event(video: bytes | str,
                     title: str,
                     metadata: Optional[dict] = None
                     ) -> Optional[str]:
    """
    Send a video event to RH. The video can be a path to a video file or a bytes object.

    :param video: Path to a video file or a bytes object.
    :param title: Title of the video event.
    :param metadata: Overlay metadata to be displayed on the video.
    :return: The event ID. None if the event failed to send.
    """
    event = robothub_core.EVENTS.prepare()
    video_bytes = Path(video).read_bytes() if isinstance(video, str) else video
    event.add_video(video_bytes, f'Video event {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', metadata)
    event.set_title(title)
    robothub_core.EVENTS.upload(event)
    _log_event_status(True, event.id)
    return event.id
