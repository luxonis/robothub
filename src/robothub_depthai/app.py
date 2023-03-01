import robothub

from robothub_depthai.manager import HubCameraManager

__all__ = ['RobotHubApplication']


class RobotHubApplication(robothub.RobotHubApplication):
    """
    Wrapper for robothub.RobotHubApplication to add DepthAI specific functionality.
    """

    def __init__(self):
        super().__init__()
        self.camera_manager = HubCameraManager()

    def start_execution(self) -> None:
        self.camera_manager.start()

    def on_stop(self) -> None:
        try:
            self.camera_manager.stop()
        except AttributeError:
            pass

    @property
    def unbooted_cameras(self) -> list:
        return self.camera_manager.unbooted_cameras

    @property
    def booted_cameras(self) -> list:
        return self.camera_manager.booted_cameras
