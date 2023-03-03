from .camera import *
from .neural_network import *
from .stereo import *


class Streamable:
    def __init__(self) -> None:
        self.stream_enabled = False
        self.stream_name = None
        self.stream_key = None

    def stream_to_hub(self, name: str, unique_key: str = None) -> None:
        self.stream_enabled = True
        self.stream_name = name
        self.stream_key = unique_key
