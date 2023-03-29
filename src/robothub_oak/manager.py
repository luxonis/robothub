import contextlib
import logging
import logging as log
import os
from typing import Optional, List

import robothub

from robothub_oak.device import Device
from robothub_oak.hub_camera import HubCamera

__all__ = ['DeviceManager', 'DEVICE_MANAGER']


class NoDevicesException(Exception):
    pass


class DeviceManager:
    """
    A manager class to handle multiple HubCamera instances.
    """
    REPORT_FREQUENCY = 10  # seconds
    POLL_FREQUENCY = 0.0005

    def __init__(self):
        self._devices = []  # Used to store all devices, shouldn't be modified in any way
        self._hub_cameras = []  # Used to store all HubCamera instances that are currently running

        self.connecting_to_device = False  # Used to prevent multiple threads from connecting to the same device
        self.stop_event = robothub.threading.Event()

        self.reporting_thread = robothub.threading.Thread(target=self._report, name='ReportingThread', daemon=False)
        self.polling_thread = robothub.threading.Thread(target=self._poll, name='PollingThread', daemon=False)
        self.connection_thread = robothub.threading.Thread(target=self._connect, name='ConnectionThread', daemon=False)

    def __exit__(self):
        self.stop()

    def start(self) -> None:
        """
        Start the cameras, start reporting and polling threads.
        """

        # Endless loop to prevent app from exiting if no devices are found
        while not self.stop_event.is_set():
            if self._devices:
                break

            self.stop_event.wait(5)

        self.connection_thread.start()
        log.info('Device connection thread: started successfully.')

        self.reporting_thread.start()
        log.info('Reporting thread: started successfully.')

        self.polling_thread.start()
        log.info('Polling thread: started successfully.')

        while not self.stop_event.is_set():
            self.stop_event.wait(60)

    def stop(self) -> None:
        """
        Stop the cameras, stop reporting and polling threads.
        """
        log.debug('Threads: gracefully stopping...')
        self.stop_event.set()

        self.__graceful_thread_join(self.connection_thread)
        self.__graceful_thread_join(self.reporting_thread)
        self.__graceful_thread_join(self.polling_thread)

        try:
            robothub.STREAMS.destroy_all_streams()
        except BaseException as e:
            raise Exception(f'Destroy all streams excepted with: {e}.')

        for camera in self._hub_cameras:
            try:
                if camera.state != robothub.DeviceState.DISCONNECTED:
                    with open(os.devnull, 'w') as devnull:
                        with contextlib.redirect_stdout(devnull):
                            camera.stop()
            except BaseException as e:
                raise Exception(f'Device {camera.device_name}: could not exit with exception: {e}.')

        log.info('App: stopped successfully.')

    def add_device(self, device: 'Device') -> None:
        """
        Add a camera to the list of cameras.
        """
        self._devices.append(device)

    def remove_device(self, device: 'Device') -> None:
        """
        Remove a camera from the list of cameras.
        """
        self._devices.remove(device)

    @property
    def devices(self) -> List['Device']:
        """
        Returns the list of cameras.
        """
        return self._devices

    def _report(self) -> None:
        """
        Reports the state of the cameras to the agent. Active when app is running, inactive when app is stopped.
        Reporting frequency is defined by REPORT_FREQUENCY.
        """
        while not self.stop_event.is_set():
            for camera in self._hub_cameras:
                try:
                    device_info = camera.info_report()
                    device_stats = camera.stats_report()

                    robothub.AGENT.publish_device_info(device_info)
                    robothub.AGENT.publish_device_stats(device_stats)
                except Exception as e:
                    log.debug(f'Device {camera.device_name}: could not report info/stats with error: {e}.')

            self.stop_event.wait(self.REPORT_FREQUENCY)

    def _poll(self) -> None:
        """
        Polls the cameras for new detections. Polling frequency is defined by POLL_FREQUENCY.
        """
        while not self.stop_event.is_set():
            for camera in self._hub_cameras:
                if not camera.poll():
                    self._disconnect_camera(camera)
                    continue

            self.stop_event.wait(self.POLL_FREQUENCY)

    def _connect(self) -> None:
        """
        Reconnects the cameras that were disconnected or reconnected.
        """
        while not self.stop_event.is_set():
            if len(self._hub_cameras) == len(self._devices) or self.connecting_to_device:
                self.stop_event.wait(5)
                continue

            mxids = [camera.device_name for camera in self._hub_cameras]
            for device in self._devices:
                if device.mxid not in mxids:
                    self.connecting_to_device = True
                    self._connect_device(device)
                    self.connecting_to_device = False

    def _connect_device(self, device: 'Device') -> None:
        """
        Connect a device to the app.
        """
        hub_camera = HubCamera(device_name=device.get_device_name())
        if not device._start(hub_camera):  # Initialize the device (create streams, etc.)
            hub_camera.stop()
            return

        hub_camera.start()  # Start the pipeline

        device.connect_callback(hub_camera)
        self._hub_cameras.append(hub_camera)

        logging.info(f'Device {device.get_device_name()}: started successfully.')

    def _disconnect_camera(self, camera: HubCamera) -> None:
        """
        Disconnect a device from the app.
        """
        log.info(f'Device {camera.device_name}: disconnected.')
        camera.stop()
        self._hub_cameras.remove(camera)

        device = self._get_device_by_name(camera.device_name)
        if device:
            device.disconnect_callback(camera)

    def _get_device_by_name(self, name: str) -> Optional['Device']:
        """
        Get a device by its mxid.
        """
        for device in self._devices:
            if device.get_device_name() == name:
                return device

        return None

    @staticmethod
    def __graceful_thread_join(thread) -> None:
        """
        Gracefully stop a thread.
        """
        try:
            if thread.is_alive():
                thread.join()
        except BaseException as e:
            log.error(f'{thread.getName()}: join excepted with: {e}.')

    @staticmethod
    def get_device(id: str = None, name: str = None, mxid: str = None, ip_address: str = None) -> Device:
        """
        Returns a device by its ID, name, mxid or IP address.

        :param id: The ID of the device.
        :param name: The name of the device.
        :param mxid: The mxid of the device.
        :param ip_address: The IP address of the device.
        :return: The device.
        """
        assert id or name or mxid or ip_address, 'Must specify at least one of id, name, mxid or ip_address'

        device = Device(id=id, name=name, mxid=mxid, ip_address=ip_address)
        if device not in DEVICE_MANAGER.devices:
            DEVICE_MANAGER.add_device(device)
        return device

    @staticmethod
    def get_all_devices() -> List[Device]:
        """
        Returns all devices.

        :return: All devices.
        """
        devices = []
        for obj in robothub.DEVICES:
            device = Device(mxid=obj.oak['serialNumber'])
            if device not in DEVICE_MANAGER.devices:
                DEVICE_MANAGER.add_device(device)
            devices.append(device)

        return devices


DEVICE_MANAGER = DeviceManager()
