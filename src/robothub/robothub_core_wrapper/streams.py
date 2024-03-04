"""Contains classes and methods for streaming to App's Frontend server and the Cloud."""
import json
import logging as log
import os
import time
from base64 import b64encode
from queue import Queue
from threading import Event, Thread
from typing import Dict

__all__ = ['Streams', 'StreamHandle', 'STREAMS']


class Streams:
    """Handles video streams"""
    streams: Dict[str, 'StreamHandle']

    def __init__(self):
        self.streams = {}
        self._wish_responses = {}
        self._agent_client = None

    def _bind_agent_(self, agent):
        self._agent_client = agent

    def _wait_for_wish_response(self, wish_id, time_limit=5, check_interval=0.1):
        now = time.time()
        last_time = now + time_limit
        while time.time() <= last_time:
            if wish_id in self._wish_responses:
                return True
            # Wait for check interval seconds, then check again.
            time.sleep(check_interval)
        return False

    def create_video(self, camera_serial: str, unique_key: str, description: str) -> 'StreamHandle':
        """
        Creates a stream and returns its L{StreamHandle}

        @param camera_serial: Serial number (MxID) of camera requesting the stream
        @type camera_serial: str
        @param unique_key: Key identifying the stream. Must be unique for each created stream, else an exception is thrown.
        @type unique_key: str
        @param description: Name of the stream in the cloud. Does not have to be unique.
        @type description: str
        """

        if not isinstance(camera_serial, str): raise TypeError('camera_serial must be a string')
        if not isinstance(unique_key, str): raise TypeError('unique_key must be a string')
        if not isinstance(description, str): raise TypeError('description must be a string')

        if unique_key in self.streams:
            raise ValueError(f'Stream with id {unique_key} already exists')

        return StreamHandle(self._agent_client, unique_key, camera_serial, description, "dummy_fifo_path")

    def destroy(self, stream: 'StreamHandle'):
        """
        Deletes a stream and its L{StreamHandle}.

        @param stream: key of stream to be destroyed
        @type stream: L{StreamHandle}
        """
        if stream.unique_key not in self.streams:
            raise ValueError(f'Stream with id {stream.unique_key} does not exist')

        stream = self.streams.pop(stream.unique_key)
        stream._destroy()
        self._agent_client._notify_stream_destroyed([stream.unique_key])
        del stream

    def destroy_streams_by_id(self, stream_ids: list):
        """
        Destroys streams corresponding to {stream_ids}, throws if any of the corresponding streams does not exist.

        @param stream_ids: Keys of streams to be destroyed
        @type stream_ids: List[str]
        """
        for stream_id in stream_ids:
            if not isinstance(stream_id, str):
                raise TypeError(f'Given stream id:', stream_id, 'Is not a string')
            if stream_id not in self.streams:
                raise ValueError(f'Stream with id {stream_id} does not exist')
            stream = self.streams.pop(stream_id)
            stream._destroy()
            del stream
        self._agent_client._notify_stream_destroyed(stream_ids)

    def destroy_all_streams(self):
        """
        Destroys all streams.
        """
        all_streams = list(self.streams.keys())
        if len(all_streams) == 0:
            return
        for stream_id in all_streams:
            stream = self.streams.pop(stream_id)
            stream._destroy()
            del stream
        self._agent_client._notify_stream_destroyed(all_streams)


class StreamHandle:
    """
    Used for handling an open stream

    @param camera_serial: Serial number (MxID) of camera the stream is registered for
    @type camera_serial: str
    @param unique_key: Unique Key identifying the stream
    @type unique_key: str
    @param description: Name of the stream in the cloud
    @type description: str
    """
    def __init__(self, agent_client: 'AgentClient', unique_key: str, camera_serial: str, description: str, fifo_path):
        self._agent_client = agent_client

        self.unique_key = unique_key
        """Unique Key identifying the stream"""
        self.camera_serial = camera_serial
        """Serial number (MxID) of camera the stream is registered for"""
        self.description = description
        """Name of the stream in the cloud"""

        self._fifo_path = fifo_path

        self._write_queue = Queue()
        self._stop_event = Event()
        self._write_thread = Thread(target=self._write_loop, name='StreamHandleWriteThread', daemon=False)
        self._write_thread.start()

    def _write_loop(self):
        while not self._stop_event.is_set():
            if not self._write_queue.empty():
                stream_packet = self._write_queue.get()
                if len(stream_packet) > 2097152:
                    log.warning(f"Packet of size {len(stream_packet)} of stream with unique key \"{self.unique_key}\" was not sent! Maximum size of packets is limited to 2 MB.")
                else:
                    pass
            self._stop_event.wait(timeout=0.001)

    def _write_stream_packet(self, payload: bytearray | bytes, sizeof_payload: int, timestamp: int, metadata: dict = None):
        header = {'content_bytes': sizeof_payload, 'time': timestamp}
        if metadata:
            assert isinstance(metadata, dict), "metadata must be either a JSON-serializable dictionary or None"
            metadata = b64encode(json.dumps(metadata).encode('utf-8')).decode('utf-8')
            header['metadata'] = metadata
        else:
            header['metadata'] = ''
        header_encoded = (json.dumps(header) + '\n\n').encode('utf-8')
        # Send header and payload
        self._write_queue.put(bytes(header_encoded) + bytes(payload), block=True)

    def publish_video_data(self, video_data: bytes | bytearray, timestamp: int, metadata: dict | None = None):
        """
        Used to send a frame with a corresponding timestamp. Optionally, metadata to be rendered over the frame can be included.

        @param video_data: Bytes of the encoded frame. Encoding must be H264.
        @type video_data: bytes | bytearray
        @param timestamp: Timestamp of the frame. Does not have to correspond to when frame was taken on device, but must be increasing with each subsequent frame.
        @type timestamp: int
        """

        if not isinstance(video_data, (bytes, bytearray)):
            raise TypeError(f'"video_data" must of type bytes or bytearray')
        if not isinstance(timestamp, int):
            raise TypeError(f'"timestamp" must be an integer')
        payload = video_data
        sizeof_payload = len(video_data)
        self._write_stream_packet(payload, sizeof_payload, timestamp, metadata)

    def _destroy(self):
        self._stop_event.set()
        self._write_thread.join()

STREAMS = Streams()
"""Instance of B{Streams} class, initialized at App startup."""
