"""
Mediates communication between App and Agent. Contains mainly internal methods.
"""

import json
import os
import sys
from time import time
import uuid
from select import select, poll, POLLIN
from base64 import b64encode, b64decode
from typing import Dict

from queue import Queue

from robothub.app import threading
from robothub.events import FutureEvent, UploadedEvent
from robothub._exceptions import RobotHubFatalException

__all__ = ['AgentClient', 'AGENT']

import logging as log
log.basicConfig(format = '%(levelname)s | %(funcName)s:%(lineno)s => %(message)s', level = log.INFO)

class AgentClient:
    """
    Internally used to communicate with agent, send / receive messages over (FIFO) / STDIN (JSON serialized objects)
    """

    def __init__(self):
        log.debug('AGENT INIT')
        self._write_fd = os.open('/fifo/app2agent', os.O_WRONLY | os.O_APPEND)
        # self.visualization_fd = os.open('/fifo/visualize', os.O_WRONLY | os.O_APPEND)
        self._MSG_SEPARATOR = b'\n'

        # Listen to the incoming messages
        self._stop_event = threading.Event()
        self._listen_thread = threading.Thread(target=self._listen, name='AgentListenThread', daemon=False)

        # Create message queue for self.write_thread to send messages through
        self._msg_queue = Queue()
        self._write_thread = threading.Thread(target=self._write, name='AgentWriteThread', daemon=False)

        self._blocking_responses: Dict[str, dict] = {}  # id to response mapping for blocking responses
        self._blocking_requests = set() # set of id's of blocking requests
        self._active_wishes: Dict[str, dict] = {} # id to wish
        log.debug('AGENT INITIALIZED')

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
        log.debug('AGENT shutdown')
        try:
            self._stop()
        except BaseException as e:
            log.debug(f'set stop event excepted with {e}')
        try:
            self._listen_thread.join()
            log.debug('Listen thread joined')
        except BaseException as e:
            log.debug(f'Listen thread join excepted with {e}')
        try:
            self._write_thread.join()
            log.debug('Write thread joined')
        except BaseException as e:
            log.debug(f'Write thread join excepted with {e}')
        try:
            os.close(self._write_fd)
            log.debug('Write file descriptor closed')
        except BaseException as e:
            log.debug(f'Close write file descriptor excepted with {e}')
        try:
            os.close(self._visualization_fd)
            log.debug('Visualization file descriptor closed')
        except BaseException as e:
            log.debug(f'Close visualization file descriptor excepted with {e}')
        log.debug('AGENT shutdown complete')

    def _stop(self):
        self._stop_event.set()
        log.debug(f'stop event set')

    def _restart_app(self, blocking: bool = False):
        """Used by RobotHubApplication.restart"""
        self._send_wish('restart', blocking = blocking)

    def restart_host(self, blocking: bool = False):
        log.error("This method is DEPRECATED and will be REMOVED. Use App's \'restart_host\' method instead.")
        """Deprecated method, replaced by L{RobotHubApplication.restart_host}. Sends a request to Agent to restart Host."""
        self._send_wish('restart_host', blocking = blocking)

    def shutdown_host(self, blocking: bool = False):
        log.error("This method is DEPRECATED and will be REMOVED. Use App's \'shutdown_host\' method instead.")
        """Deprecated method, replaced by L{RobotHubApplication.shutdown_host}. Sends a request to Agent to stop Host."""
        self._send_wish('shutdown_host', blocking = blocking)

    def _restart_host(self, blocking: bool = False):
        """Sends a request to Agent to restart Host."""
        self._send_wish('restart_host', blocking = blocking)

    def _shutdown_host(self, blocking: bool = False):
        """Sends a request to Agent to shutdown Host."""
        self._send_wish('shutdown_host', blocking = blocking)

    def _send_start_notification(self):
        self._send_notification('started')

    def classify_detection(self, detection_id: str, classification: str, blocking: bool = False):
        """
        Deprecated method, replaced by self.classify_event

        Sends a classification for Event with id equal to {detection_id}.
        """
        log.warn("This method is DEPRECATED and will be REMOVED. Use the \"classify_event\" method instead.")
        self._send_wish('classify_detection',
            body={'detection_id': detection_id, 'classification': classification},
            blocking=blocking,
        )

    def classify_event(self, event_id: str, classification: str, blocking: bool = False):
        # TODO get a better docstring for this
        """
        Sends a classification for an Event with id equal to {event_id}.
        """
        self._send_wish('classify_detection',
            body={'detection_id': detection_id, 'classification': classification},
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

        @param device_info: Dictionary containing device stats
        @type device_info: dict
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
        log.debug('ENTRY')
        fn = sys.stdin.fileno()
        sys.stdin = os.fdopen(fn)

        poller = poll()
        poller.register(sys.stdin, POLLIN)

        while not self._stop_event.is_set():
            while sys.stdin in select([sys.stdin], [], [], 0.01)[0]:
                line = sys.stdin.readline()
                if line:
                    data = self._decode_msg(line)
                    log.debug(f"MESSAGE RECEIVED FROM AGENT: {json.dumps(data)}")

                    if 'what' not in data:
                        log.error(f'Invalid message: {json.dumps(data)}')
                        raise Exception('Missing "what" value received in message from agent')

                    if data['what'] == 'notification':
                        self._handle_notification(data)
                    elif data['what'] == 'request':
                        self._handle_request(data)
                    elif data['what'] == 'detection':
                        self._handle_detection_response(data)
                    elif data['what'] == 'session_started':
                        self._handle_session_started(data)
                    elif data['what'] == 'session_ended':
                        self._handle_session_ended(data)
                    elif data['what'] == 'devices_changed':
                        self._handle_devices_changed(data)
                    elif data['what'] == 'wish':
                        self._handle_wish_response(data)
                        if data['id'] in self._blocking_requests:
                            self._blocking_requests.remove(data['id'])
                            self._blocking_responses[data['id']] = data
                    elif data['what'] == 'app-frontend':
                        self._communicator._handle(data)
                    else:
                        log.error(f'Invalid message: {json.dumps(data)}')
                        raise Exception('Unknown "what" value received in message from agent')
                    # If a line was read, wait 0.01. 
                    self._stop_event.wait(0.01)

    def _wait_for_response(self, request_id, time_limit=5, check_interval=0.1):
        now = time()
        last_time = now + time_limit

        while time() <= last_time:
            if self._stop_event.is_set():
                return False
            if request_id in self._blocking_responses.keys():
                self._blocking_responses.pop(request_id)
                return True
            # Wait for check interval seconds, then check again.
            self._stop_event.wait(check_interval)
        return False

    def _send_notification(self, type: str, body: list | dict | str | None = None) -> None:
        # body needs to be JSON serializable
        if body:
            message = {'what': 'notification', 'type': type, 'body': body}
        else:
            message = {'what': 'notification', 'type': type}
        self._send_msg(message)

    def _send_wish(self, type: str, body: dict | str | None = None, blocking: bool = False) -> str | None:
        wish_id = self._generate_id()
        message = {'what': 'wish', 'id': wish_id, 'type': type}
        if body:
            message['body'] = body
        self._active_wishes[wish_id] = message
        self._send_msg(message)
        if blocking:
            self._handle_blocking_behaviour(wish_id, f'Blocking wish with type {type}: no response from agent')
        else:
            return wish_id

    def _send_detection(self, detection: 'FutureEvent', blocking: bool = False) -> None:
        detection_id = detection.id
        message = {'what': 'detection', 'id': detection_id, 'body': detection._to_msg_format()}
        self._send_msg(message)

    def _handle_notification(self, notification: dict) -> None:
        if notification['type'] == 'TBD':
            pass

    def _handle_session_started(self, msg: dict) -> None:
        assert msg.get('session_id') is not None, 'Session Started Message received from FE is invalid: missing or null "session_id" attribute'
        session_id = msg.get('session_id')
        try:
            self._communicator._handle_session_started(session_id)
        except AttributeError as e:
            #Except AttributeError if self._communicator is undefined, else throw
            log.debug(f'Handle session started failed with: {e}')

    def _handle_session_ended(self, msg: dict) -> None:
        assert msg.get('session_id') is not None, 'Session Ended Message received from FE is invalid: missing or null "session_id" attribute'
        session_id = msg.get('session_id')
        try:
            self._communicator._handle_session_ended(session_id)
        except AttributeError as e:
            #Except AttributeError if self._communicator is undefined, else throw
            log.debug(f'Handle session ended failed with: {e}')

    def _handle_devices_changed(self, msg: dict) -> None:
        try:
            self._communicator._handle_devices_changed()
        except AttributeError as e:
            #Except AttributeError if self._communicator is undefined, else throw
            log.debug(f'Handle devices changed failed with: {e}')

    def _handle_request(self, request: dict) -> None:
        req_type = request['type']
        if req_type == 'stop_app':
            self._app._stop()
        else:
            raise RobotHubFatalException('Invalid request type')

    def _handle_wish_response(self, wish_response: dict) -> bool:
        original_wish = self._active_wishes.pop(wish_response['id'])
        if original_wish['type'] == 'create_stream':
            self._streams._wish_responses[wish_response['id']] = wish_response
        elif (original_wish['type'] == 'shutdown_host') or \
                (original_wish['type'] == 'classify_detection') or \
                (original_wish['type'] == 'restart_host') or \
                (original_wish['type'] == 'restart') or \
                (original_wish['type'] == 'configure_wifi'):
            if wish_response['action'] == 'rejected':
                log.debug(f'Agent rejected wish of type \"{original_wish["type"]}\" with reason {wish_response["reason"]}')
                return False
            else:
                log.debug(f'Agent granted wish \"{str(original_wish["type"])}\"')
                return True
        else:
            raise RobotHubFatalException(f'Agent received response "{str(wish_response)}" for invalid wish "{str(original_wish)}"')

    def _handle_detection_response(self, detection_response: dict) -> None:
        action = detection_response.get('action')
        if action == 'accepted':
            pass
        elif action == 'rejected':
            log.info(f'Event \"{detection_response["id"]}\" rejected with reason \"{detection_response["reason"]}\"')
        elif action == 'uploaded':
            assert detection_response.get('id') is not None, 'Event uploaded response invalid: missing "id" attribute'
            assert type(detection_response.get('body')) == dict, 'Event uploaded response invalid: invalid body'
            assert detection_response.get('body').get('robothub_web_url') is not None, 'Event uploaded response invalid: body is missing "robothub_web_url" attribute'
            assert detection_response.get('body').get('tags') is not None, 'Event uploaded response invalid: body is missing "tags" attribute'
            uploaded_detection = UploadedEvent(detection_response.get('id'), detection_response.get('body').get('robothub_web_url'), detection_response.get('body').get('public_access'), detection_response.get('body').get('tags'))
            # Check if on_detection_uploaded is defined and callable
            try:
                if callable(self._app.on_detection_uploaded):
                    deprecated_callback_defined = True
                else:
                    raise RobotHubFatalException("app.on_detection_uploaded is a reserved name for a deprecated method, check the docs for more information")
            except AttributeError:
                deprecated_callback_defined = False

            if deprecated_callback_defined == True:
                # If on_detection_uploaded (or both on_detection_uploaded and on_event_uploaded) is defined, call it and warn user
                log.warn('"on_detection_uploaded" method is DEPRECATED and will be UNSUPPORTED in future versions of robothub_core. Define method "on_event_uploaded" instead!')
                self._app.on_detection_uploaded(uploaded_detection)
            else:
                # on_detection_uploaded is correctly undefined, use on_event_uploaded
                self._app.on_event_uploaded(uploaded_detection)
        else:
            log.error('Invalid Event response message: ' + str(detection_response))
            raise Exception('Event response with invalid action received from agent')

    def _send_msg(self, message: dict) -> None:
        self._msg_queue.put(message)

    def _send_visualization(self, image_data: bytearray, label: str, content_type = 'image/png', metadata: str = None):
        header = {'content_type': content_type, 'label': label}
        header_encoded = self._encode_msg(header)
        try:
            image_encoded = b64encode(image_data)
        except BaseException as e:
            raise RuntimeError(f'Image with header could not be encoded with error {e}, aborting sending visualization')

        # Send header and image data
        os.write(self._visualization_fd, bytes(header_encoded) + b'\n\n' + bytes(image_encoded) + b'\n')

    def _write(self):
        log.debug('ENTRY')
        while not self._stop_event.is_set():
            if not self._msg_queue.empty():
                msg = self._msg_queue.get()
                self._write_dict_to_fd(msg)
            self._stop_event.wait(timeout = 0.01)
        log.debug('EXIT')

    def _write_dict_to_fd(self, message: dict) -> None:
        if not isinstance(message, dict):
            raise RuntimeError(f'Message must be type "dict", not type "{type(message)}"')
        enc_message = self._encode_msg(message) + self._MSG_SEPARATOR
        if len(enc_message) > 8192:
            raise RuntimeError(f'Message longer than 8192 bytes: "{len(enc_message)}"')
        os.write(self._write_fd, enc_message)

    def _handle_blocking_behaviour(self, request_id: str, error_message: str, time_limit=5):
        self._blocking_requests.add(request_id)
        status = self._wait_for_response(request_id, time_limit=time_limit)
        if not status:
            raise Exception(error_message)

    def _encode_msg(self, dict_object: dict) -> bytes:
        """Serialize dictionary as a JSON string, encode it with utf-8, then encode it with b64"""
        try:
            enc_msg = b64encode(json.dumps(dict_object).encode('utf-8'))
            return enc_msg
        except:
            raise RuntimeError(f'message could not be serialized')

    def _decode_msg(self, message: str) -> dict:
        """Decode message with b64, then decode it with utf-8, then de-serialize it from JSON to dict"""
        try:
            dec_msg = json.loads(b64decode(message).decode('utf-8'))
            return dec_msg
        except:
            raise RuntimeError(f'message could not be decoded')

    @staticmethod
    def _generate_id() -> str:
        """Return hashed timestamp"""
        return str(uuid.uuid4())

AGENT = AgentClient()
