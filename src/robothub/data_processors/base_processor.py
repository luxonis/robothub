from abc import abstractmethod, ABC

__all__ = ['BaseDataProcessor']


class BaseDataProcessor(ABC):
    """
    Base class for data processors. Data processors are used to process data from cameras,
    and are called when new data is available.
    """

    @abstractmethod
    def process_packets(self, packets: dict):
        pass

    def __call__(self, *args, **kwargs):
        self.process_packets(*args, **kwargs)
