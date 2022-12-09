import robothub

from robothub_depthai.manager import HubCameraManager

__all__ = ['RobotHubApplication']


class RobotHubApplication(robothub.RobotHubApplication):
    """
    Wrapper for robothub.RobotHubApplication to add DepthAI specific functionality.
    """

    def __init__(self):
        super().__init__()
        self.camera_manager = HubCameraManager(self, robothub.DEVICES)

    def start_execution(self) -> None:
        self.camera_manager.start()

    def on_stop(self) -> None:
        self.camera_manager.stop()

    @property
    def hub_cameras(self) -> list:
        return self.camera_manager.hub_cameras
