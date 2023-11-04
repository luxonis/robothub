import datetime
import itertools
import logging
import uuid
from collections import deque
from pathlib import Path
from queue import Queue, Empty
from typing import Callable, Optional

from depthai_sdk.recorders.video_writers import AvWriter

try:
    import av
except ImportError:
    av = None

logger = logging.getLogger(__name__)


class FrameBuffer:
    def __init__(self, maxlen: int = None):
        """
        A buffer for storing frames.

        :param maxlen: The maximum number of frames to store in the buffer. If None, the buffer will be unbounded.
        """
        self.buffer = deque(maxlen=maxlen)
        self.temporary_queues = set()

    def get_slice(self, start: int, end: int | None = None) -> list:
        """
        Get a slice of the buffer.

        :param start: Start index.
        :param end: End index. If None, return all elements from `start` to the end of the buffer.
        :return: Slice of the buffer.
        """
        return list(itertools.islice(self.buffer, int(start), end))

    def save_video(self,
                   before_seconds: int,
                   after_seconds: int,
                   fps: int,
                   frame_width: int,
                   frame_height: int,
                   on_complete: Optional[Callable] = None,
                   delete_after_complete: bool = False
                   ) -> str | None:
        """
        Save a video of the last `before_seconds` seconds and the next `after_seconds` seconds.

        :param before_seconds: Number of seconds to save before the current time.
        :param after_seconds: Number of seconds to save after the current time.
        :param fps: The FPS of the video.
        :param frame_width: Video frame width.
        :param frame_height: Video frame height.
        :param on_complete: Callback function to call when the video is ready. Path to the video file will be passed as the first argument.
        :param delete_after_complete: If True, delete the video file after the callback function is called. Default: False.
        """
        if not av:
            raise ImportError('av library is not installed. Cannot save video. '
                              'Please make sure PyAV is installed (`pip install pyav`).')

        if before_seconds < 0 or after_seconds < 0:
            raise ValueError('`before_seconds` and `after_seconds` must be non-negative.')
        if before_seconds * fps > self.buffer.maxlen:
            raise ValueError('`before_seconds` is too large. The buffer does not contain enough frames.')

        # Get frames before the current time
        video_frames_before = self.get_slice(start=self.buffer.maxlen - before_seconds * fps)
        video_frames_after = []
        temp_queue = Queue()
        self.temporary_queues.add(temp_queue)
        latest_t_before = video_frames_before[-1].msg.getTimestampDevice()

        # Get frames after the current time
        while True:
            try:
                p = temp_queue.get(block=True, timeout=2.0)
                timestamp = p.msg.getTimestampDevice()
                if timestamp > latest_t_before:
                    video_frames_after.append(p)
                if timestamp - latest_t_before > datetime.timedelta(seconds=after_seconds):
                    break
            except Empty:
                pass

        self.temporary_queues.remove(temp_queue)
        video_path = self._mux_video(packets=video_frames_before + video_frames_after[:int(after_seconds * fps)],
                                     fps=fps,
                                     frame_width=frame_width,
                                     frame_height=frame_height)

        if on_complete:
            on_complete(video_path)
        if on_complete and delete_after_complete:
            Path(video_path).unlink()
            return None

        return video_path

    @staticmethod
    def _mux_video(packets: list,
                   fps: int,
                   frame_width: int,
                   frame_height: int,
                   ) -> str | None:
        """
        Mux a list of packets into a video file and return the path to the video file.
        """
        dir_path = Path(f'/tmp/robothub-videos/{uuid.uuid4().hex}')
        dir_path.mkdir(parents=True)
        name = str(uuid.uuid4().hex)
        av_writer = AvWriter(path=Path(dir_path),
                             name=name,
                             fourcc='h264',
                             fps=fps,
                             frame_shape=(frame_width, frame_height))

        for p in packets:
            av_writer.write(p.msg)

        av_writer.close()
        video_path = Path(dir_path, name).with_suffix('.mp4')
        return str(video_path)

    def default_callback(self, packet) -> None:
        """
        Default callback for the frame buffer. It will append the packet to the buffer and put it in all temporary queues.
        """
        self.buffer.append(packet)
        for q in self.temporary_queues:
            q.put(packet)

    @property
    def maxlen(self) -> int:
        return self.buffer.maxlen
