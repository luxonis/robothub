import robothub

from robothub_oak.manager import DEVICE_MANAGER


class DefaultApplication(robothub.RobotHubApplication):
    def on_start(self):
        devices = DEVICE_MANAGER.get_all_devices()
        for device in devices:
            color_resolution = '1080p'
            mono_resolution = '400p'

            color = device.get_camera('color', resolution=color_resolution, fps=30)
            color.stream_to_hub(name=f'Color stream {device.id}')

            stereo = device.get_stereo_camera(resolution=mono_resolution, fps=30)
            stereo.stream_to_hub(name=f'Stereo stream {device.id}')

    def start_execution(self):
        DEVICE_MANAGER.start()

    def on_stop(self):
        DEVICE_MANAGER.stop()