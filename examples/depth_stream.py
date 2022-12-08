import logging as log

import robothub

from robothub_depthai.manager import HubCameraManager
from robothub_depthai.app import RobotHubApplication

log.basicConfig(format='%(levelname)s | %(funcName)s:%(lineno)s => %(message)s', level=log.INFO)


class ExampleApplication(RobotHubApplication):
    def __init__(self):
        super().__init__()
        self.camera_manager = HubCameraManager(self, robothub.DEVICES)

    def on_start(self):
        for camera in self.hub_cameras:
            stereo = camera.create_stereo('800p', fps=30)

            # It will automatically create a stream and assign matching callback based on Component type
            camera.create_stream(component=stereo, name='depth', description='Depth stream')

    def on_stop(self):
        self.stop()

    def on_detection_uploaded(self, detection: robothub.UploadedDetection):
        log.debug(f'Detection with id "{detection.detection_id}" has been uploaded')
        log.debug(f'Uploaded detection: {str(detection.to_str())}')
