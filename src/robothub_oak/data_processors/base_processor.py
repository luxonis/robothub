from abc import ABC

__all__ = ['BaseDataProcessor']

from typing import Any


class BaseDataProcessor(ABC):
    """
    Base class for data processors. Data processors are used to process data from cameras,
    and are called when new data is available.
    """

    def process_packets(self, packets: Any) -> None:
        """
        This method is called every time pipeline outputs new data.

        :param packets: Either a single packet or a dictionary of packets.
        """
        pass

    def __call__(self, *args, **kwargs):
        self.process_packets(*args, **kwargs)
