import logging as log
import time
from threading import Thread
from typing import List

import robothub
from robothub import RobotHubApplication

from robothub_depthai.hub_camera import HubCamera

__all__ = ['HubCameraManager']


class HubCameraManager:
    """
    A manager class to handle multiple HubCamera instances.
    """
    REPORT_FREQUENCY = 10  # seconds
    POLL_FREQUENCY = 0.002

    def __init__(self, app: RobotHubApplication, devices: List[dict]):
        """
        :param app: The RobotHubApplication instance.
        :param devices: A list of devices to be managed.
        """
        self.hub_cameras = [HubCamera(app, device_mxid=device.oak['serialNumber'], id=i)
                            for i, device in enumerate(devices)]
        self.app = app

        self.reporting_thread = Thread(target=self._report, name='ReportingThread', daemon=False)
        self.polling_thread = Thread(target=self._poll, name='PollingThread', daemon=False)

    def __exit__(self):
        self.stop()

    def start(self) -> None:
        """
        Start the cameras, start reporting and polling threads.
        """
        print('Starting cameras...')
        for camera in self.hub_cameras:
            camera.start()

        print('Starting reporting thread...')
        self.reporting_thread.start()
        print('Reporting thread started successfully')

        print('Starting polling thread...')
        self.polling_thread.start()
        print('Polling thread started successfully')

        print('Cameras started successfully')

    def stop(self) -> None:
        """
        Stop the cameras, stop reporting and polling threads.
        """
        print('Gracefully stopping threads...')
        self.app.stop_event.set()

        try:
            while self.reporting_thread.is_alive():
                time.sleep(0.2)
        except BaseException as e:
            log.error(f'self.reporting_thread.is_alive() excepted with: {e}')

        try:
            while self.polling_thread.is_alive():
                time.sleep(0.2)
        except BaseException as e:
            log.error(f'self.polling_thread.is_alive() excepted with: {e}')

        try:
            robothub.AGENT.shutdown()
        except BaseException as e:
            log.debug(f'Agent shutdown excepted with {e}')

        try:
            robothub.STREAMS.destroy_all_streams()
        except BaseException as e:
            raise Exception(f'Destroy all streams excepted with: {e}')

        for camera in self.hub_cameras:
            try:
                if camera.state != robothub.DeviceState.DISCONNECTED:
                    camera.oak_camera.__exit__(Exception, 'Device disconnected - app shutting down', None)
            except BaseException as e:
                raise Exception(f'Could not exit device with error: {e}')

        log.debug('App stopped successfully')

    def _report(self) -> None:
        """
        Reports the state of the cameras to the agent. Active when app is running, inactive when app is stopped.
        Reporting frequency is defined by REPORT_FREQUENCY.
        """
        while not self.app.stop_event.is_set():
            for camera in self.hub_cameras:
                device_info = camera.info_report()
                device_info |= {'state': camera.state.value}  # DAI SDK holds no state
                device_stats = camera.stats_report()

                robothub.AGENT.publish_device_info(device_info)
                robothub.AGENT.publish_device_stats(device_stats)

            time.sleep(self.REPORT_FREQUENCY)

    def _poll(self) -> None:
        """
        Polls the cameras for new detections. Polling frequency is defined by POLL_FREQUENCY.
        """
        while self.app.stop_event.is_set():
            for camera in self.hub_cameras:
                camera.poll()

            time.sleep(self.POLL_FREQUENCY)
