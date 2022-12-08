import robothub

from robothub_depthai.manager import HubCameraManager

class RobotHubApplication(robothub.RobotHubApplication):
    def __init__(self):
        super().__init__()
        self.camera_manager = HubCameraManager(self, robothub.DEVICES)

    def start_execution(self):
        self.camera_manager.start()

    def stop(self):
        self.camera_manager.stop()

    @property
    def hub_cameras(self):
        return self.camera_manager.hub_cameras
