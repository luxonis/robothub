"""
Mediates communication between App and Agent. Contains mainly internal methods.
"""

import json
import os
import uuid
from base64 import b64decode, b64encode
from queue import Queue
from typing import Dict

from robothub.robothub_core_wrapper.app import threading
from robothub.robothub_core_wrapper.events import FutureEvent

__all__ = ['AgentClient', 'AGENT']

import logging as log


class AgentClient:
    """
    Internally used to communicate with agent, send / receive messages over (FIFO) / STDIN (JSON serialized objects)
    """

    def __init__(self):

        # Listen to the incoming messages
        self._stop_event = threading.Event()
        self._listen_thread = threading.Thread(target=self._listen, name='AgentListenThread', daemon=False)

        # Create message queue for self.write_thread to send messages through
        self._msg_queue = Queue()
        self._write_thread = threading.Thread(target=self._write, name='AgentWriteThread', daemon=False)

        self._blocking_responses: Dict[str, dict] = {}  # id to response mapping for blocking responses
        self._blocking_requests = set()  # set of id's of blocking requests
        self._active_wishes: Dict[str, dict] = {}  # id to wish

    def _bind_app_(self, app: 'RobotHubApplication'):
        self._app = app

    def _bind_streams_(self, streams: 'Streams'):
        self._streams = streams

    def _bind_communicator_(self, communicator: 'Communicator'):
        self._communicator = communicator
        # Communicator is defined -> start accepting messages from frontend
        self._listen_thread.start()
        self._write_thread.start()

    def _shutdown(self):
        log.debug('Agent client shutdown called')
        self._stop()
        self._listen_thread.join()
        log.debug('Listen thread joined')
        self._write_thread.join()
        log.debug('Write thread joined')
        try:
            os.close(self._write_fd)
            log.debug('Write file descriptor closed')
        except Exception as e:
            log.debug(f'Close write file descriptor excepted with {e}')
        log.debug('Agent client shutdown complete')

    def _stop(self):
        self._stop_event.set()
        log.debug(f'Agent client stop event is set')

    def _send_start_notification(self):
        self._send_notification('started')

    def classify_event(self, event_id: str, classification: str, blocking: bool = False):
        """
        Sends a classification for an Event with id equal to {event_id}.
        """
        self._send_wish('classify_detection',
                        body={'detection_id': event_id, 'classification': classification},
                        blocking=blocking,
                        )

    def publish_device_info(self, device_info: dict):
        """
        Publishes device info. C{device_info} needs to be a properly formatted dictionary.

        @param device_info: Dictionary containing device info
        @type device_info: dict
        """
        # TODO better docstring, add a type check
        self._send_notification('dai_device_info', [device_info])

    def publish_device_stats(self, device_stats: dict):
        """
        Publishes device stats. C{device_stats} needs to be a properly formatted dictionary.

        @param device_stats: Dictionary containing device stats
        @type device_stats: dict
        """
        # TODO better docstring, add a type check
        self._send_notification('dai_device_stats', [device_stats])

    def _create_stream(self, unique_key: str, stream_name: str, camera_mxid: str):
        payload = {
            'unique_key': unique_key,
            'name': stream_name,
            'camera_serial': camera_mxid,
        }
        return self._send_wish('create_stream', payload)

    def _notify_stream_destroyed(self, destroyed_streams: list):
        self._send_notification('streams_destroyed', destroyed_streams)

    def _listen(self) -> None:
        log.debug('Agent client listen thread not available in local environment')

    def _send_notification(self, type: str, body: list | dict | str | None = None) -> None:
        # body needs to be JSON serializable
        if body:
            message = {'what': 'notification', 'type': type, 'body': body}
        else:
            message = {'what': 'notification', 'type': type}
        self._send_msg(message)

    def _send_msg(self, message: dict) -> None:
        log.debug(f"Message ignored in local environment: {str(message)}")

    def _send_wish(self, *args, **kwargs) -> None:
        log.debug(f"send_wish not available in local environment")

    def _send_detection(self, detection: 'FutureEvent', blocking: bool = False) -> None:
        detection_id = detection.id
        message = {'what': 'detection', 'id': detection_id, 'body': detection._to_msg_format()}
        self._send_msg(message)

    def _send_visualization(self, image_data: bytearray, label: str, content_type='image/png', metadata: str = None):
        header = {'content_type': content_type, 'label': label}
        header_encoded = self._encode_msg(header)
        try:
            image_encoded = b64encode(image_data)
        except Exception as e:
            raise RuntimeError(f'Image with header could not be encoded with error {e}, aborting sending visualization')
        log.info(f"send_visualization not available in local environment")

    def _write(self):
        log.debug('Agent client write thread not available in local environment')

    def _write_dict_to_fd(self, message: dict) -> None:
        pass

    def _encode_msg(self, dict_object: dict) -> bytes:
        """Serialize dictionary as a JSON string, encode it with utf-8, then encode it with b64"""
        try:
            enc_msg = b64encode(json.dumps(dict_object).encode('utf-8'))
            return enc_msg
        except Exception:
            raise RuntimeError(f'message could not be serialized')

    def _decode_msg(self, message: str) -> dict:
        """Decode message with b64, then decode it with utf-8, then de-serialize it from JSON to dict"""
        try:
            dec_msg = json.loads(b64decode(message).decode('utf-8'))
            return dec_msg
        except Exception:
            raise RuntimeError(f'message could not be decoded')

    @staticmethod
    def _generate_id() -> str:
        """Return hashed timestamp"""
        return str(uuid.uuid4())


AGENT = AgentClient()
