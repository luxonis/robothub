import robothub

from robothub_oak.manager import DEVICE_MANAGER


class Application(robothub.RobotHubApplication):
    def on_start(self):
        devices = DEVICE_MANAGER.get_all_devices()
        for device in devices:
            color = device.get_camera('color', resolution='1080p', fps=30)
            color.stream_to_hub(name=f'Color stream {device.id}')

            stereo = device.get_stereo_camera(resolution='400p', fps=30)
            stereo.stream_to_hub(name=f'Stereo stream {device.id}')

            nn = device.create_neural_network('person-detection-retail-0013', color)
            nn.stream_to_hub(name=f'NN stream {device.id}')

    def start_execution(self):
        DEVICE_MANAGER.start()

    def on_stop(self):
        DEVICE_MANAGER.stop()
