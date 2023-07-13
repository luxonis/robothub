import logging as log
import zipfile
from io import BytesIO
from typing import Union, Optional, List

import cv2
import numpy as np
import robothub_core

__all__ = ['send_robothub_image_event', 'send_frame_event_with_zipped_images']


def _log_event_status(result: bool, event_id):
    if result:
        log.info(f"Event {event_id}: sent successfully.")
    else:
        log.info(f'Event {event_id}: failed to send.')


def send_robothub_image_event(image: Union[np.ndarray, bytes],
                              device_id: str,
                              title: str,
                              metadata: Optional[dict] = None,
                              tags: List[str] = None,
                              mjpeg_quality=98,
                              encode=False
                              ) -> Optional[str]:
    """Send a single image frame event to RH."""

    if tags is None:
        tags = []
    try:
        if encode:
            _, image = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), mjpeg_quality])

        event = robothub_core.EVENTS.prepare()
        event.add_frame(bytes(image), device_id)
        event.set_title(title)
        event.set_metadata(metadata)
        event.add_tags(tags)
        robothub_core.EVENTS.upload(event)
        _log_event_status(True, event.id)
        return event.id
    except Exception as e:
        log.error(f'Failed to send event: {e}')
        _log_event_status(False, "None")
        return None


def send_frame_event_with_zipped_images(cv_frame,
                                        files,
                                        title: str,
                                        device_id: str,
                                        tags: List[str] = None,
                                        metadata: Optional[dict] = None,
                                        encode: bool = False,
                                        mjpeg_quality=98
                                        ) -> Optional[str]:
    """Send a collection of images as a single event to RH."""
    try:
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), mjpeg_quality]
        if encode:
            _, cv_frame = cv2.imencode('.jpg', cv_frame, encode_param)

        event = robothub_core.EVENTS.prepare()
        event.add_frame(bytes(cv_frame), device_id)
        event.set_title(title)
        event.set_tags(tags)
        event.set_metadata(metadata)
        log.debug(f'Total files: {len(files)}')
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
    except Exception as e:
        log.error(f'Failed to send event: {e}')
        _log_event_status(False, 'None')
        return None
