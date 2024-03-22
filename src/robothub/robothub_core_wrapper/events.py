"""Defines methods for sending Events to the cloud."""

import logging as log
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, TypedDict, Union
from uuid import uuid4

from robothub.robothub_core_wrapper._event_typechecks import *

__all__ = ['Events', 'FutureEvent', 'UploadedEvent', 'EVENTS'] # Deprecated DETECTIONS


class Events:
    """Used to prepare Events for agent to consume and inform agent via AgentClient"""

    def __init__(self):
        self._folder = Path("/storage/detections")

    def _bind_agent_(self, agent):
        self._agent_client = agent

    def prepare(self) -> 'FutureEvent':
        """
        Creates a new empty Event.

        @return: An empty Event of type L{FutureEvent}
        """

        event_id = str(uuid4())
        folder = Path(self._folder, event_id)
        return FutureEvent(event_id, folder)

    def upload(self, event: 'FutureEvent'):
        """
        Uploads an Event.

        @param event: Event to be uploaded.
        @type event: L{FutureEvent}
        """
        if event._sent is True:
            raise RuntimeError('Event was already sent')
        else:
            event._sent = True
            log.info(f"Event ignored in local environment: {str(event)}")
            self._agent_client._send_detection(event)

    def send_frame_event(self, imagedata: bytes | bytearray, camera_serial: str, title: str | None = None, frame_name: str | None = None, frame_metadata: dict | None = None) -> None:
        """
        Creates and immediately uploads an Event with a single frame. Does not allow for full customization of the Event.

        @param imagedata: The encoded frame bytes
        @type imagedata: bytes | bytearray
        @param camera_serial: Serial number (MxID) of camera that took the picture
        @type camera_serial: str
        @param title: Optional title for the Event
        @type title: str | NoneType
        @param frame_name: Optional name for the frame, does not define the filename
        @type frame_name: str | NoneType
        @param frame_metadata: metadata of valid format will be visualized over the frame in the cloud. Optional.
        @type frame_metadata: dict | NoneType
        """

        event = self.prepare()
        event.add_frame(imagedata, camera_serial, frame_name, frame_metadata)
        event.set_title(title)
        self.upload(event)

    def send_video_event(self, video: bytes | bytearray, title: str | None = None, video_name: str | None = None, video_metadata: dict | None = None) -> None:
        """
        Creates and immediately uploads an Event with a single video. Does not allow for full customization of the Event.

        @param video: The encoded video bytes. Encoding must be H264.
        @type video: bytes | bytearray
        @param title: Optional title for the Event
        @type title: str | NoneType
        @param video_name: Optional name for the video, does not define the filename
        @type video_name: str | NoneType
        @param video_metadata: Metadata of valid format will be visualized over the video in the cloud. Optional.
        @type video_metadata: dict | NoneType
        """

        event = self.prepare()
        event.add_video(video, video_name, video_metadata)
        event.set_title(title)
        self.upload(event)

    def send_binary_file_event(self, binary_data: bytes | bytearray, title: str | None = None, file_name: str | None = None) -> None:
        """
        Creates and immediately uploads an Event with a file of arbitrary type. Does not allow for full customization of the Event.

        @param binary_data: The file in bytes
        @type binary_data: bytes | bytearray
        @param title: Optional title for the Event
        @type title: str | NoneType
        @param file_name: Optional name for the file, does not define the filename
        @type file_name: str | NoneType
        """

        event = self.prepare()
        event.add_file(binary_data, file_name)
        event.set_title(title)
        self.upload(event)

    def send_text_file_event(self, text: str, title: str | None = None, text_name: str | None = None) -> None:
        """
        Creates and immediately uploads an Event with a single string. Does not allow for full customization of the Event.

        @param text: The text in string form
        @type text: str
        @param text: The text in string form
        @type text: str
        @param title: Optional title for the Event
        @type title: str | NoneType
        @param text_name: Optional name for the text
        @type text_name: str | NoneType
        """
        text_bytes = bytes(text.encode('utf-8'))

        event = self.prepare()
        event.add_file(text_bytes, text_name)
        event.set_title(title)
        self.upload(event)


class FutureEvent:
    """Object describing an Event"""
    id: str
    """ID of the Event"""
    folder_path: Union[str, Path]
    """Path to the folder of the Event in the App's container. Added frames, files & videos are stored in this folder."""

    def __init__(self, _id: str, folder_path: Union[str, Path]):
        self.id = _id
        self.folder_path = folder_path
        self._sent = False

        self.title = 'Event: ' + _id
        """Title of the Event in the Cloud. Set to \"Event\" + UUID by default."""
        self.__videos = []
        """List containing all videos in this Event."""
        self.__frames = []
        """List containing all frames in this Event."""
        self.__files = []
        """List containing all files in this Event."""
        self.__metadata: Dict[str, Any] = {}
        """Metadata of the Event, empty dictionary by default."""
        self.__tags: List[str] = []
        """Tags of the Event, empty list by default."""

        # Flags
        self._keep_after_upload = False
        self._no_upload_by_default = False
        self._keep_when_space_low = False

    def add_video(self, _bytes: bytes | bytearray, name: str | None = None, metadata: dict | None = None, filename: str | None = None, camera_serial: str | None = None):
        """
        Adds a video to the Event.

        @param _bytes: Bytes of the encoded video. Must be H264 format.
        @type _bytes: bytes | bytearray
        @param name: Optional - Name of the video
        @type name: str | NoneType
        @param metadata: Optional - Metadata to be overlayed over the video. List length must be equal to number of frames in the video.
        @type metadata: list
        @param filename: Optional - can define name of the video file on Host.
        @type filename: str | NoneType
        @param camera_serial: Optional - Serial number (MxID) of camera that took the video
        @type camera_serial: str
        """
        if len(self.__videos) >= 1:
            raise RuntimeError('Cannot add more than 1 video to an Event')
        # type checks
        _check_video_format(_bytes)
        _check_args(name, camera_serial, filename)
        # autogenerate names if necessary
        name, filename = _check_names(name, filename, 'video')

        path = Path(self.folder_path, filename)
        self._write_bytes_to_file(_bytes, path)
        event_object = {"path": str(path), "name": name, "camera_serial": camera_serial}

        if metadata is not None:
            _check_video_metadata(metadata)
            metadata_filename = filename + '.rh_metadata'
            metadata_path = Path(self.folder_path, metadata_filename)
            self._write_metadata_to_file(metadata, metadata_path)
            event_object['metadata'] = True
        else:
            event_object['metadata'] = False

        self.__videos.append(event_object)

    def add_frame(self, _bytes, camera_serial: str | None = None, name: str | None = None, metadata: dict | None = None, filename: str | None = None):
        """
        Adds a frame to the Event.

        @param _bytes: Bytes of the encoded frame
        @type _bytes: bytes | bytearray
        @param camera_serial: Optional - Serial number (MxID) of camera that took the frame
        @type camera_serial: str
        @param name: Optional - Name of the frame
        @type name: str | NoneType
        @param metadata: Optional - Metadata to be overlayed over the frame
        @type metadata: list
        @param filename: Optional - can define name of the frame file on Host.
        @type filename: str | NoneType
        """
        if len(self.__frames) >= 10:
            raise RuntimeError('Cannot add more than 10 frames to an Event')
        # type checks
        _check_frame_format(_bytes)
        _check_args(name, camera_serial, filename)

        # autogenerate names if necessary
        name, filename = _check_names(name, filename, 'frame')

        path = Path(self.folder_path, filename)
        self._write_bytes_to_file(_bytes, path)
        event_object = {"path": str(path), "name": name, "camera_serial": camera_serial}

        if metadata is not None:
            _check_frame_metadata(metadata)
            metadata_filename = filename + '.rh_metadata'
            metadata_path = Path(self.folder_path, metadata_filename)
            self._write_metadata_to_file(metadata, metadata_path)
            event_object['metadata'] = True
        else:
            event_object['metadata'] = False
        self.__frames.append(event_object)

    def add_file(self, _bytes, name: str | None = None, filename: str | None = None):
        """
        Adds a file to the Event.

        @param _bytes: Bytes of the file.
        @type _bytes: bytes | bytearray
        @param name: Optional - Name of the file in the cloud
        @type name: str | NoneType
        @param filename: Optional - can define name of the file saved on Host.
        @type filename: str | NoneType
        """
        if len(self.__files) >= 10:
            raise RuntimeError('Cannot add more than 10 files to an Event')
        # type checks
        _check_file_format(_bytes)
        _check_args(name, None, filename)
        # autogenerate names if necessary
        name, filename = _check_names(name, filename, 'file')

        path = Path(self.folder_path, filename)
        self._write_bytes_to_file(_bytes, path)
        event_object = {"path": str(path), "name": name}
        self.__files.append(event_object)

    def add_existing_file(
            self,
            filename: Path | str,
            copy: bool = True,
            name: str | None = None,
    ):
        """
        Adds an existing file to the Event.

        @param filename: Path to the file to be added.
        @type filename: Path | str
        @param copy: If True, the file will be copied to the Event folder. If False, the file will be moved to the Event folder.
        @type copy: bool
        @param name: Optional - Name of the file in the cloud
        @type name: str | NoneType
        """
        if len(self.__files) >= 10:
            raise RuntimeError('Cannot add more than 10 files to an Event')
        filename = Path(filename)
        if not filename.is_file():
            raise FileNotFoundError(f'file \"{filename}\" does not exist or is not a file')

        stem = filename.name.split(".", maxsplit=1)[0]
        suffix = "".join(filename.suffixes)
        dst = Path(self.folder_path, filename.name)
        if dst.exists():
            dst = dst.with_name(f"{stem}__{str(uuid4())}{suffix}")
        if not name:
            name = stem

        event_object = {"path": str(dst), "name": name}
        self.__files.append(event_object)

    def set_title(self, title):
        """
        Sets the title of the Event.

        @param title: Title for the Event
        @type title: str | NoneType
        """
        if isinstance(title, str):
            if title != "":
                self.title = title
            else:
                raise RuntimeError("Cannot set title to an empty string.")
        else:
            raise TypeError("Title must be a string.")

    def set_metadata(self, metadata: dict):
        """
        Sets the metadata of the Event.

        @param metadata: Dictionary containing the metadata
        @type metadata: dict
        """
        if isinstance(metadata, (dict, type(None))):
            if metadata != {}:
                self.__metadata = metadata
            else:
                raise RuntimeError("Cannot set metadata to an empty dictionary.")
        else:
            raise TypeError("Metadata must be None or a dictionary.")

    def add_tag(self, tag: str):
        """
        Adds a tag to the Event.

        Cannot add more than 10 tags to one Event.

        @param tag: The tag string
        @type tag: str
        """
        if len(self.__tags) >= 10:
            raise RuntimeError("Cannot add more than 10 tags to an Event.")

        if isinstance(tag, str):
            self.__tags.append(tag)
        else:
            raise TypeError("Tag must be a string.")

    def add_tags(self, tags: List[str]):
        """
        Adds multiple tags to the Event.

        Cannot add more than 10 tags to one Event.

        @param tags: A list of tags
        @type tags: List[str]
        """
        current_length = len(self.__tags)
        extra_length = len(tags)
        if current_length + extra_length >= 10:
            raise RuntimeError('An Event cannot have more than 10 tags.')
        for tag in tags:
            if isinstance(tag, str):
                pass
            else:
                raise TypeError('All added tags must be strings.')
        self.__tags.extend(tags)

    def set_tags(self, tags: List[str]):
        """
        Sets the tags of the Event.

        An Event cannot have more than 10 tags.

        @param tags: A list of tags
        @type tags: List[str]
        """
        if len(tags) >= 10:
            raise RuntimeError('An Event cannot have more than 10 tags.')
        for tag in tags:
            if isinstance(tag, str):
                pass
            else:
                raise TypeError('All tags must be strings.')
        self.__tags = tags

    @property
    def keep_after_upload(self) -> bool:
        """
        Decides whether Event should be kept after upload, C{False} by default.

        Example usage:

        >>> self.keep_after_upload
        True

        return: bool
        """
        return self._keep_after_upload

    @keep_after_upload.setter
    def keep_after_upload(self, value: bool):
        """
        Sets the keep after upload property.

        Example usage:

        >>> self.keep_after_upload = True
        """
        self._keep_after_upload = value

    @property
    def no_upload_by_default(self) -> bool:
        # TODO test what this actually does
        """
        If set to True, Event will not be uploaded. C{False} by default.

        Example usage:

        >>> self.no_upload_by_default
        True

        return: bool
        """
        return self._no_upload_by_default

    @no_upload_by_default.setter
    def no_upload_by_default(self, value: bool):
        """
        Sets the keep after upload property.

        Example usage:

        >>> self.keep_after_upload = True
        """
        self._no_upload_by_default = value

    @property
    def keep_when_space_low(self) -> bool:
        """
        Decides whether Event should be kept when storage space is low, C{False} by default.

        Example usage:

        >>> self.keep_after_upload
        True

        return: bool
        """
        return self._keep_when_space_low

    @keep_when_space_low.setter
    def keep_when_space_low(self, value: bool):
        """
        Sets the keep when space low property.

        Example usage:

        >>> self.keep_when_space_low = True
        """
        self._keep_when_space_low = value

    def _to_msg_format(self):
        """Returns whole Event in dictionary format"""
        return {
            'title': self.title,
            'tags': self.__tags,
            'frames': self.__frames,
            'files': self.__files,
            'video': self.__videos,
            'metadata': self.__metadata,
            'keep_after_upload': self.keep_after_upload,
            'no_upload_by_default': self.no_upload_by_default,
            'keep_when_space_low': self.keep_when_space_low
        }

    def _write_metadata_to_file(self, metadata: dict, path: Path) -> None:
        log.info(f"Writing metadata to file is not available in local environment.")

    def _write_bytes_to_file(self, _bytes: bytes, path: Path) -> None:
        log.info(f"Writing to file is not available in local environment.")
        return


class UploadedEventPublicAccess(TypedDict):
    """Object that describes public access (without credentials) to an uploaded Event."""
    domain: str
    """Domain of the robot"""
    token: str
    """Token which allows limited time access to the Event"""


@dataclass
class UploadedEvent:
    """Contains information about an uploaded Event, has no methods. Automatically sent as input to App's \"on_event_uploaded\" method."""
    event_id: str
    """ID of the Event"""
    robothub_url: str
    """URL of the Event, accessible only with credentials"""
    public_access: Union[UploadedEventPublicAccess, None]
    """Object allowing public access"""
    tags: List[str]
    """List of tags of the Event"""


EVENTS = Events()
