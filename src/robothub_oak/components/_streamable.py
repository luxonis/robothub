from typing import Callable

from robothub_oak.packets import HubPacket


class Streamable:
    """
    Auxiliary class for components that can be streamed to the hub.
    """

    def __init__(self) -> None:
        self.stream_enabled = False
        self.stream_name = None
        self.stream_key = None
        self.visualizer_callback = None

    def stream_to_hub(self,
                      name: str,
                      unique_key: str = None,
                      visualizer_callback: Callable[[HubPacket], None] = None
                      ) -> None:
        """
        Enables streaming of this component to the RobotHub.

        :param name: Name of the stream to be displayed on the RobotHub.
        :param unique_key: Unique key of the stream. If not provided, it will be generated automatically.
        :param visualizer_callback: Callback that will be called when a new packet is received. The main intention of
            this callback is to allow the user to visualize the data in a custom way.
        """
        self.stream_enabled = True
        self.stream_name = name
        self.stream_key = unique_key
        self.visualizer_callback = visualizer_callback
