"""Handles communication with App's frontend server"""

from abc import ABC
import json
from typing import Any, Callable
from uuid import uuid4
import time
from threading import Thread
from dataclasses import dataclass

__all__ = ['Communicator', 'CommunicatorResponse', 'COMMUNICATOR']

import logging as log
log.basicConfig(format = '%(levelname)s | %(funcName)s:%(lineno)s => %(message)s', level = log.INFO)

@dataclass
class CommunicatorResponse:
    """Responses to requests from App are instances of this class"""
    sessionId: str | None
    """ID of specific session, can be None"""
    payload: Any
    """Response payload, structure defined by user"""

class Communicator(ABC):
    """Handles communication with App's frontend server"""
    # TODO add type checking for parameters
    def __init__(self):
        self._session_start_cb = None
        self._session_end_cb = None
        self._notification_cb = None
        self._request_cb = None
        self._devices_changed_cb = None
        self._async_requests = {} # id -> (timeout, callback) mapping for async requests
        self._sync_requests = set() # set of id's of yet unanswered requests
        self._responses = {} # id -> json mapping
        self._timeout_async_thread = Thread(target = self._timeout_async, name = 'TimeoutAsyncRequestsThread', daemon=False)

    @staticmethod
    def _generate_id() -> str:
        """Return hashed timestamp"""
        return str(uuid4())

    def _bind_agent_(self, agent):
        self._agent = agent

    def _bind_app_(self, app):
        self._app = app
        self._timeout_async_thread.start()

    def _timeout_async(self):
        while not self._app.stop_event.is_set():
            async_reqs_copy = self._async_requests.copy() # Get a shallow copy, so that dict doesnt change during iteration
            for key in async_reqs_copy.keys():
                if time.time() > async_reqs_copy[key][0]:
                    # async request timed out
                    try:
                        self._async_requests.pop(key)
                        log.debug(f'Async Request with id "{key}" timed out')
                    except KeyError as e:
                        # race condition - response was received after timeout and request was processed
                        pass
                self._app.wait(0.01)
            self._app.wait(1)

    def notify(self, key: str, payload: str | list | dict | None, target: str | None = None) -> None:
        """
        Sends a notification to the FE server.

        @param key: Used to define different types of notifications
        @type key: str
        @param payload: Content of the notification
        @type payload: str | list | dict | None
        @param target: If target is a valid session ID, notification is sent to the specific session. If None, notification is broadcast.
        @type target: str | None
        """
        # TODO check what happens if you use wrong session ID (with requests too), as there is no good way to check its still valid
        notification = {
            'what': 'app-frontend',
            'type': 'notification',
            'target': target,
            'msg_key': key,
            'msg_payload': payload,
            'msg_content': 'json' if type(payload) == dict else 'Any',
        }
        log.debug(f'Sending FE Notification {str(notification)}')
        self._agent._send_msg(notification)

    def request(self, key: str, payload: str | list | dict | None, target: str | None = None, timeoutSeconds: float | int = 30) -> CommunicatorResponse | bool:
        """
        Sends a request to the FE server and blocks until a response is received or until timeout. 

        @param key: Used to define different types of requests
        @type key: str
        @param payload: Content of the request
        @type payload: str | list | dict | None
        @param target: If target is a valid session ID, request is sent to the specific session. If None, request is broadcast.
        @type target: str | None
        @param timeoutSeconds: Timeout length in seconds.
        @type timeoutSeconds: float | int
        """
        request_id = self._generate_id()
        request = {
            'what': 'app-frontend',
            'id': request_id,
            'type': 'request',
            'target': target,
            'msg_key': key,
            'msg_payload': payload,
            'msg_content': 'json' if type(payload) == dict else 'Any',
        }
        self._sync_requests.add(request_id)
        self._agent._send_msg(request)
        log.debug(f'Sending FE Sync Request {str(request)}')

        now = time.time()
        last_time = now + timeoutSeconds
        while (time.time() <= last_time) and (self._app.running):
            if request_id in self._responses:
                self._sync_requests.remove(request_id)
                response = self._responses.pop(request_id)
                return CommunicatorResponse(response['session_id'] if 'session_id' in response.keys() else None, response['payload'])
            # Wait for check interval seconds, then check again.
            time.sleep(0.1)
        log.debug(f'Sync Request for FE timed out: {str(request)}')
        self._sync_requests.remove(request_id)
        return False

    def requestAsync(self, key: str, payload: Any, target: str | None = None, timeoutSeconds = 30, on_response: Callable[[Any], None] | None = None) -> None:
        """
        Sends an asynchronous request to the FE server, calls a callback on the response if a response is received before timeout.

        @param key: Used to define different types of requests
        @type key: str
        @param payload: Content of the request
        @type payload: str | list | dict | None
        @param target: If target is a valid session ID, request is sent to the specific session. If None, request is broadcast.
        @type target: str | None
        @param timeoutSeconds: Timeout length in seconds.
        @type timeoutSeconds: float | int
        @param on_response: Callback to be invoked on the response. 
        @type on_response: Callable[[Any], None]
        """

        request_id = self._generate_id()
        request = {
            'what': 'app-frontend',
            'id': request_id,
            'type': 'request',
            'target': target,
            'msg_key': key,
            'msg_payload': payload,
            'msg_content': 'json' if type(payload) == dict else 'TBD',
        }
        self._async_requests[request_id] = (time.time() + timeoutSeconds, on_response)
        self._agent._send_msg(request)
        log.debug(f'Sending FE Async Request {str(request)}')

    def on_frontend(self, session_start: Callable | None = None, session_end: Callable | None = None, notification: Callable | None = None, request: Callable | None = None) -> None:
        # TODO add type definition of parameters
        """
        Sets callbacks for session start & end, notifications and requests from the FE server.

        @param session_start: Callback for "session started" messages from FE
        @type session_start: Callable
        @param session_end: Callback for "session ended" messages from FE
        @type session_end: Callable
        @param notification: Callback for notifications from FE
        @type notification: Callable
        @param request: Callback for requests from FE
        @type request: Callable
        """
        if session_start:
            if callable(session_start):
                self._session_start_cb = session_start
            else:
                raise TypeError('Session start callback is not callable!')
        if session_end:
            if callable(session_end):
                self._session_end_cb = session_end 
            else:
                raise TypeError('Session end callback is not callable!')
        if notification:
            if callable(notification):
                self._notification_cb = notification 
            else:
                raise TypeError('Notification callback is not callable!')
        if request:
            if callable(request):
                self._request_cb = request 
            else:
                raise TypeError('Request callback is not callable!')

    def set_devices_changed_cb(self, devices_changed_cb: Callable) -> None:
        # TODO add type definition of parameter
        """
        Sets the device change callback. 

        This function will be called each time configuration of any assigned device changes.
        @param devices_changed_cb: Callback for requests from FE
        @type devices_changed_cb: Callable

        """
        if callable(devices_changed_cb):
            self.devices_changed_cb = devices_changed_cb
        else:
            raise TypeError('Device change callback is not callable!')

    def _handle_session_started(self, session_id):
        if self._session_start_cb:
            self._session_start_cb(session_id)

    def _handle_session_ended(self, session_id):
        if self._session_end_cb:
            self._session_end_cb(session_id)

    def _handle_devices_changed(self):
        if self._devices_changed_cb is not None:
            self._devices_changed_cb()

    def _handle(self, payload):
        #log.debug(f'Handling message from FE: {str(payload)}')
        session_id = payload['session_id']
        data = payload['data']

        if (data['what'] == 'ping'):
            log.debug(f'Sending pong to FE request')
            self._agent._send_msg({
                'what': 'app-frontend',
                'id': data['id'],
                'type': 'pong',
                'target': session_id,
                'msg_key': data['key'],
                'msg_payload': {},
                'msg_content': 'json',
            })
        elif (data['what'] == 'notification'):
            if self._notification_cb:
                self._notification_cb(session_id, data['key'], data['payload'])
        elif (data['what'] == 'request'):
            if self._request_cb:
                response = self._request_cb(session_id, data['key'], data['payload'])
                log.debug(f'Sending response to FE request: {str(response)}')
                self._agent._send_msg({
                    'what': 'app-frontend',
                    'id': data['id'],
                    'type': 'response',
                    'target': session_id,
                    'msg_key': data['key'],
                    'msg_payload': response,
                    'msg_content': 'json',
                })
        elif (data['what'] == 'response'):
            self._handle_response(data)
        else:
            log.error(f'Invalid message: {json.dumps(data)}')
            raise Exception('Unknown "what" value received in message from frontend')

    def _handle_response(self, data):
        if data['id'] in self._async_requests:
            try:
                original_request = self._async_requests.pop(data['id'])
            except:
                # race condition - request timed out, even though we have response 
                return
            response_cb = original_request[1]
            if response_cb:
                # If response cb was defined, check if its callable and call it
                if callable(response_cb):
                    response = CommunicatorResponse(data['session_id'] if 'session_id' in data.keys() else None, data['payload'])
                    response_cb(response)
                else:
                    log.warn(f'User-defined callback of type {type(response_cb)} for asynchronous request is not callable')
            log.debug(f'FE response to app\'s Async Request {data["id"]} handled ')

        elif data['id'] in self._sync_requests:
            # id belongs to sync request
            self._responses[data['id']] = data
        else:
            # id belongs to timed out async request
            pass

COMMUNICATOR = Communicator()
"""Instance of Communicator class initialized at startup."""
