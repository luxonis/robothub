class Streamable:
    """
    Auxiliary class for components that can be streamed to the hub.
    """
    def __init__(self) -> None:
        self.stream_enabled = False
        self.stream_name = None
        self.stream_key = None

    def stream_to_hub(self, name: str, unique_key: str = None) -> None:
        self.stream_enabled = True
        self.stream_name = name
        self.stream_key = unique_key
