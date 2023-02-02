import logging as log
import os
import contextlib
import time
from typing import List

import robothub

import robothub_depthai
from robothub_depthai.hub_camera import HubCamera

__all__ = ['HubCameraManager']


class NoDevicesException(Exception):
    pass


class HubCameraManager:
    """
    A manager class to handle multiple HubCamera instances.
    """
    REPORT_FREQUENCY = 10  # seconds
    POLL_FREQUENCY = 0.002

    def __init__(self, app: 'robothub_depthai.RobotHubApplication', devices: List[dict]):
        """
        :param app: The RobotHubApplication instance.
        :param devices: A list of devices to be managed.
        """
        self.hub_cameras = []
        self.devices = devices
        self.app = app
        self._update_hub_cameras(devices)

        self.lock = robothub.threading.Lock()
        self.reporting_thread = robothub.threading.Thread(target=self._report, name='ReportingThread', daemon=False)
        self.polling_thread = robothub.threading.Thread(target=self._poll, name='PollingThread', daemon=False)
        self.connection_thread = robothub.threading.Thread(target=self._connect, name='ConnectionThread', daemon=False)

    def __exit__(self):
        self.stop()

    def _update_hub_cameras(self, devices) -> None:
        """
        Connect the cameras.
        """
        for i, device in enumerate(devices):
            mxid = device.oak['serialNumber']
            if mxid in [camera.device_mxid for camera in self.hub_cameras]:
                continue

            hub_camera = HubCamera(self.app, device_mxid=device.oak['serialNumber'], id=i)
            if hub_camera.oak_camera is not None:
                self.hub_cameras.append(hub_camera)

    def start(self) -> None:
        """
        Start the cameras, start reporting and polling threads.
        """
        if not self.hub_cameras:
            # Endless loop to prevent app from exiting if no devices are found
            while True:
                self.app.wait(1)

        log.info('Cameras: starting...')
        for camera in self.hub_cameras:
            camera.start()

        log.info('Reporting thread: starting...')
        self.reporting_thread.start()
        log.info('Reporting thread: started successfully')

        log.info('Polling thread: starting...')
        self.polling_thread.start()
        log.info('Polling thread: started successfully')

        log.info('Device connection thread: starting...')
        self.connection_thread.start()
        log.info('Device connection thread: started successfully')

        log.info('Cameras: started successfully')

    def stop(self) -> None:
        """
        Stop the cameras, stop reporting and polling threads.
        """
        log.debug('Gracefully stopping threads...')
        self.app.stop_event.set()

        try:
            if self.reporting_thread.is_alive():
                self.reporting_thread.join()
        except BaseException as e:
            log.error(f'self.reporting_thread join excepted with: {e}')
            
        try:
            if self.polling_thread.is_alive():
                self.polling_thread.join()
        except BaseException as e:
            log.error(f'self.polling_thread join excepted with: {e}')

        try:
            robothub.STREAMS.destroy_all_streams()
        except BaseException as e:
            raise Exception(f'Destroy all streams excepted with: {e}')

        for camera in self.hub_cameras:
            try:
                if camera.state != robothub.DeviceState.DISCONNECTED:
                    with open(os.devnull, 'w') as devnull:
                        with contextlib.redirect_stdout(devnull):
                            camera.oak_camera.__exit__(Exception, 'Device disconnected - app shutting down', None)
            except BaseException as e:
                raise Exception(f'Could not exit device with error: {e}')

        log.info('App stopped successfully')

    def _report(self) -> None:
        """
        Reports the state of the cameras to the agent. Active when app is running, inactive when app is stopped.
        Reporting frequency is defined by REPORT_FREQUENCY.
        """
        while self.app.running:
            for camera in self.hub_cameras:
                try:
                    device_info = camera.info_report()
                    device_stats = camera.stats_report()

                    robothub.AGENT.publish_device_info(device_info)
                    robothub.AGENT.publish_device_stats(device_stats)
                except Exception as e:
                    log.debug(f'Could not report device ({camera.device_mxid}) info/stats: {e}')

            time.sleep(self.REPORT_FREQUENCY)

    def _poll(self) -> None:
        """
        Polls the cameras for new detections. Polling frequency is defined by POLL_FREQUENCY.
        """
        while self.app.running:
            for camera in self.hub_cameras:
                if not camera.poll():
                    log.info(f'Camera {camera.device_mxid} was disconnected.')
                    self._remove_camera(camera)
                    continue

            time.sleep(self.POLL_FREQUENCY)

    def _remove_camera(self, camera: HubCamera) -> None:
        """
        Removes a camera from the list of cameras.
        :param camera: The camera to remove.
        """
        with self.lock:
            try:
                self.hub_cameras.remove(camera)
            except ValueError:
                pass

    def _connect(self) -> None:
        """
        Reconnects the cameras that were disconnected or reconnected.
        """
        while self.app.running:
            if len(self.hub_cameras) < len(self.devices):
                time.sleep(5)
                continue

            self._update_hub_cameras(devices=self.devices)
            self.app.on_start()
