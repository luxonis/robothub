import robothub

from robothub_depthai import CAMERA_MANAGER

__all__ = ['RobotHubApplication']


class RobotHubApplication(robothub.RobotHubApplication):
    """
    Wrapper for robothub.RobotHubApplication to add DepthAI specific functionality.
    """

    def __init__(self):
        super().__init__()

    def start_execution(self) -> None:
        CAMERA_MANAGER.start()

    def on_stop(self) -> None:
        try:
            CAMERA_MANAGER.stop()
        except AttributeError:
            pass
