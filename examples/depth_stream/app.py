from robothub_depthai.app import RobotHubApplication


class ExampleApplication(RobotHubApplication):
    def __init__(self):
        super().__init__()

    def on_start(self):
        for camera in self.hub_cameras:
            stereo = camera.create_stereo('800p', fps=30)

            # It will automatically create a stream and assign matching callback based on Component type
            camera.create_stream(component=stereo, name='depth', description='Depth stream')
