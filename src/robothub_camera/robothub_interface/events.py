import cv2
import logging as log
import traceback
import zipfile

from io import BytesIO
try:
    from robothub import EVENTS
except ModuleNotFoundError:
    from .mock_event import EVENTS


def __send_frame_event_done(result: bool, id_):
    if result:
        print(f"Event: {id_} sent successfully.")
    else:
        print(f"Failed to send event: {id_}.")


def send_robothub_image_event(image, device_id: str, title: str, metadata: dict | None = None, tags: list[str] = None, mjpeg_quality=98, encode=False) -> str:
    """Send a single image frame event to RH."""

    if tags is None:
        tags = []
    try:
        if encode:
            _, image = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), mjpeg_quality])

        event = EVENTS.prepare()
        event.add_frame(bytes(image), device_id)
        event.set_title(title)
        event.set_metadata(metadata)
        event.add_tags(tags)
        EVENTS.upload(event)
        __send_frame_event_done(True, event.id)
        return event.id
    except Exception as e:
        print(e)
        traceback.print_exc()
        __send_frame_event_done(False, "None")


def send_frame_event_with_zipped_images(cv_frame, files, title, device_id, tags, metadata, encode, mjpeg_quality=98) -> str:
    try:
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), mjpeg_quality]
        if encode:
            _, cv_frame = cv2.imencode('.jpg', cv_frame, encode_param)

        event = EVENTS.prepare()
        event.add_frame(bytes(cv_frame), device_id)
        event.set_title(title)
        event.set_tags(tags)
        event.set_metadata(metadata)
        log.info(f"FILES LENGTH = {len(files)}")
        with BytesIO() as zip_buffer:
            with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                for idx, file in enumerate(files):
                    if encode:
                        _, encoded = cv2.imencode('.jpg', file, encode_param)
                    else:
                        encoded = file
                    # Convert the numpy array to bytes
                    image_bytes = encoded.tobytes()
                    # Add the bytes to the zip file with a unique filename
                    filename = f"image_{idx}.jpeg"
                    zip_file.writestr(filename, image_bytes)
                    # event.add_file(bytes(encoded), name=f"image_{idx}.jpeg")
            # Get the bytes of the zip file
            zip_bytes = zip_buffer.getvalue()
            event.add_file(zip_bytes, name=f"images.zip")
            EVENTS.upload(event)
            __send_frame_event_done(True, event.id)
            return event.id
    except Exception as e:
        log.info(e)
        __send_frame_event_done(False, "None")
