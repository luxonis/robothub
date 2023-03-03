from robothub_depthai.components.streamable import Streamable

__all__ = ['Camera']


class Camera(Streamable):
    def __init__(self, name: str, resolution: str, fps: int) -> None:
        super().__init__()
        self.name = name
        self.resolution = resolution
        self.fps = fps

        self.camera_component = None  # type: depthai_sdk.components.CameraComponent
