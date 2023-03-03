from robothub_depthai.components.streamable import Streamable


class Stereo(Streamable):
    def __init__(self, resolution: str, fps: int) -> None:
        super().__init__()
        self.resolution = resolution
        self.fps = fps

        self.stereo_component = None  # type: depthai_sdk.components.StereoComponent
