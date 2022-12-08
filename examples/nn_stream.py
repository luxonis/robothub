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
            color = camera.create_camera('color', resolution='1080p', fps=30)
            nn = camera.create_nn('person-detection-retail-0013', input=color)

            # It will automatically create a stream and assign matching callback based on Component type
            camera.create_stream(component=nn, name='nn_stream', description='Detections stream')

    def on_stop(self):
        self.stop()

    def on_detection_uploaded(self, detection: robothub.UploadedDetection):
        log.debug(f'Detection with id "{detection.detection_id}" has been uploaded')
        log.debug(f'Uploaded detection: {str(detection.to_str())}')
