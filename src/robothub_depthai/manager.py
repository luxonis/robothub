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
        self.connected_cameras = []
        self.running_cameras = []
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
            if mxid in [camera.device_mxid for camera in self.running_cameras]:
                continue

            hub_camera = HubCamera(self.app, device_mxid=device.oak['serialNumber'], id=i)
            if hub_camera.oak_camera is not None:
                self.connected_cameras.append(hub_camera)

    def start(self) -> None:
        """
        Start the cameras, start reporting and polling threads.
        """
        log.info('Device connection thread: starting...')
        self.connection_thread.start()
        log.info('Device connection thread: started successfully.')

        # Endless loop to prevent app from exiting if no devices are found
        while True:
            if self.connected_cameras:
                break

            time.sleep(5)

        log.info('Devices: starting...')
        connected_cameras = self.connected_cameras.copy()
        for camera in connected_cameras:
            camera.start()
            self.running_cameras.append(camera)
            self.connected_cameras.remove(camera)

        log.info('Reporting thread: starting...')
        self.reporting_thread.start()
        log.info('Reporting thread: started successfully.')

        log.info('Polling thread: starting...')
        self.polling_thread.start()
        log.info('Polling thread: started successfully.')

        log.info('Devices: started successfully.')

    def manual_start(self) -> None:
        connected_cameras = self.connected_cameras.copy()
        for camera in connected_cameras:
            camera.start()
            self.running_cameras.append(camera)
            self.connected_cameras.remove(camera)
            log.info(f'Device {camera.device_mxid}: started successfully')

    def stop(self) -> None:
        """
        Stop the cameras, stop reporting and polling threads.
        """
        log.debug('Threads: gracefully stopping...')
        self.app.stop_event.set()

        try:
            if self.connection_thread.is_alive():
                self.connection_thread.join()
        except BaseException as e:
            log.error(f'Connection thread: join excepted with: {e}.')

        try:
            if self.reporting_thread.is_alive():
                self.reporting_thread.join()
        except BaseException as e:
            log.error(f'Reporting thread: join excepted with: {e}.')
            
        try:
            if self.polling_thread.is_alive():
                self.polling_thread.join()
        except BaseException as e:
            log.error(f'Polling thread: join excepted with: {e}.')

        try:
            robothub.STREAMS.destroy_all_streams()
        except BaseException as e:
            raise Exception(f'Destroy all streams excepted with: {e}.')

        for camera in self.running_cameras:
            try:
                if camera.state != robothub.DeviceState.DISCONNECTED:
                    with open(os.devnull, 'w') as devnull:
                        with contextlib.redirect_stdout(devnull):
                            camera.oak_camera.__exit__(Exception, 'Device disconnected - app shutting down', None)
            except BaseException as e:
                raise Exception(f'Device {camera.device_mxid}: could not exit with exception: {e}.')

        log.info('App: stopped successfully.')

    def _report(self) -> None:
        """
        Reports the state of the cameras to the agent. Active when app is running, inactive when app is stopped.
        Reporting frequency is defined by REPORT_FREQUENCY.
        """
        while self.app.running:
            for camera in self.running_cameras:
                try:
                    device_info = camera.info_report()
                    device_stats = camera.stats_report()

                    robothub.AGENT.publish_device_info(device_info)
                    robothub.AGENT.publish_device_stats(device_stats)
                except Exception as e:
                    log.debug(f'Device {camera.device_mxid}: could not report info/stats with error: {e}.')

            time.sleep(self.REPORT_FREQUENCY)

    def _poll(self) -> None:
        """
        Polls the cameras for new detections. Polling frequency is defined by POLL_FREQUENCY.
        """
        while self.app.running:
            for camera in self.running_cameras:
                if not camera.poll():
                    log.info(f'Device {camera.device_mxid}: disconnected.')
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
                self.running_cameras.remove(camera)
            except ValueError:
                pass

    def _connect(self) -> None:
        """
        Reconnects the cameras that were disconnected or reconnected.
        """
        while self.app.running:
            if len(self.running_cameras) == len(self.devices):
                time.sleep(5)
                continue

            self._update_hub_cameras(devices=self.devices)
            self.app.on_start()
            self.manual_start()
