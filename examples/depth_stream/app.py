import robothub

from robothub_oak.manager import DEVICE_MANAGER


class Application(robothub.RobotHubApplication):
    def on_start(self):
        devices = DEVICE_MANAGER.get_all_devices()
        for device in devices:
            stereo = device.get_stereo_camera(resolution='800p', fps=30)
            stereo.stream_to_hub(name=f'Stereo stream {device.id}')

    def start_execution(self):
        DEVICE_MANAGER.start()

    def on_stop(self):
        DEVICE_MANAGER.stop()
