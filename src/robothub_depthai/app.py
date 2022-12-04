import robothub

from robothub_depthai.manager import HubCameraManager

class RobotHubApplication(robothub.RobotHubApplication):
    def __init__(self):
        super().__init__()
        self.camera_manager = HubCameraManager(self, robothub.DEVICES)
