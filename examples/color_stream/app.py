import robothub

from robothub_oak.manager import DEVICE_MANAGER


class Application(robothub.RobotHubApplication):
    def on_start(self):
        devices = DEVICE_MANAGER.get_all_devices()
        for device in devices:
            color = device.get_camera('color', resolution='1080p', fps=30)
            color.stream_to_hub(name=f'Color stream {device.id}')

        DEVICE_MANAGER.start()

    def on_stop(self):
        DEVICE_MANAGER.stop()
