from robothub_depthai.app import RobotHubApplication


class ExampleApplication(RobotHubApplication):
    def __init__(self):
        super().__init__()

    def on_start(self):
        for camera in self.hub_cameras:
            color = camera.create_camera('color', resolution='1080p', fps=30)
            nn = camera.create_nn('person-detection-retail-0013', input=color)

            # It will automatically create a stream and assign matching callback based on Component type
            camera.create_stream(component=nn, name='nn_stream', description='Detections stream')
