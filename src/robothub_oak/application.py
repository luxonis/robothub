import atexit
import logging
import threading
import time
from abc import ABC, abstractmethod
from threading import Thread
from typing import Dict, Optional

import robothub_core
from depthai_sdk import OakCamera

from robothub_oak.utils import get_device_performance_metrics, get_device_details

__all__ = ['BaseApplication']

logger = logging.getLogger(__name__)


class BaseApplication(robothub_core.RobotHubApplication, ABC):
    """
    This class acts as the main entry point for the user, managing devices, creating pipelines,
    and polling the devices for new data. Derived classes must implement the `setup_pipeline` method.

    Attributes:
        config: The configuration settings from the robotapp.toml config file.

    Methods:
        setup_pipeline: Abstract method to be implemented by child classes. Sets up the pipeline for a device.
        on_device_connected: Optional method, called when a device is connected.
        on_device_disconnected: Optional method, called when a device is disconnected.
        on_stop: Optional method, called when the application is stopped.
    """

    def __init__(self):
        robothub_core.RobotHubApplication.__init__(self)
        ABC.__init__(self)

        self.__devices: Dict[str, Optional[OakCamera]] = {}
        self.__device_product_names: Dict[str, str] = {}
        self.__device_states: Dict[str, robothub_core.DeviceState] = {}
        self.__device_threads = []

        atexit.register(self.__cleanup)

        self.__manage_condition = threading.Condition()
        self.config = robothub_core.CONFIGURATION

    def on_start(self) -> None:
        for device in robothub_core.DEVICES:
            device_mxid = device.oak['serialNumber']
            self.__devices[device_mxid] = None
            self.__device_states[device_mxid] = robothub_core.DeviceState.DISCONNECTED

            name = device.oak.get('name', None) or device.oak.get('productName', None) or device_mxid
            self.__device_product_names[device_mxid] = name

            device_thread = Thread(target=self.__manage_device,
                                   kwargs={'device': device},
                                   name=f'connection_{device_mxid}',
                                   daemon=False)
            device_thread.start()
            self.__device_threads.append(device_thread)

    def start_execution(self) -> None:
        self.stop_event.wait()  # Keep main thread alive

    @abstractmethod
    def setup_pipeline(self, oak: OakCamera) -> None:
        """
        The entry point for the application. This method is called when a device is connected and ready to be used.

        :param oak: The device that is ready to be used.
        """
        pass

    def on_device_connected(self, oak: OakCamera) -> None:
        """
        Called when a camera is connected.

        :param oak: The camera that was connected.
        """
        pass

    def on_device_disconnected(self, mxid: str) -> None:
        """
        Called when a camera is disconnected. Opposite of on_device_connected.

        :param mxid: The mxid of the camera that was disconnected.
        """
        pass

    def __cleanup(self) -> None:
        """
        Called when the application is stopped. Registered as atexit handler.
        """
        for device_thread in self.__device_threads:
            device_thread.join()

        self.__devices.clear()
        self.__device_states.clear()

    def __manage_device(self, device: robothub_core.RobotHubDevice) -> None:
        """
        Handle the life cycle of one device.

        :param device: The device to manage.
        """
        device_mxid = device.oak['serialNumber']
        product_name = self.__device_product_names[device_mxid]
        logger.debug(f'Device {product_name}: management thread started.')

        while self.running:
            self.__manage_condition.acquire()
            # if device is not connected
            if self.__devices[device_mxid] is None or not self.__devices[device_mxid].running():
                # Make sure it is properly closed in case it disconnected during runtime
                self.__close_device(device_mxid)
                self.on_device_disconnected(device_mxid)

                # Connect to the device
                self.__connect(device_mxid)

                # If device is connected
                if self.__devices[device_mxid]:
                    logger.debug(f'Device {product_name}: creating pipeline...')

                    self.setup_pipeline(oak=self.__devices[device_mxid])
                    self.__devices[device_mxid].start(blocking=False)
                    self.on_device_connected(self.__devices[device_mxid])

                    logger.info(f'Device {product_name}: started successfully.')

                    # Threads for polling and reporting
                    polling_thread = Thread(target=self.__poll_device,
                                            args=(self.__devices[device_mxid],),
                                            daemon=True,
                                            name=f'poll_{device_mxid}')
                    polling_thread.start()

                    reporting_thread = Thread(target=self.__device_stats_reporting,
                                              args=(device_mxid,),
                                              daemon=True,
                                              name=f'stats_reporting_{device_mxid}')
                    reporting_thread.start()
                else:
                    self.__manage_condition.wait(25)

            self.__manage_condition.wait(5)
            self.__manage_condition.release()

        # Make sure device is closed
        self.__close_device(mxid=device_mxid)
        self.on_device_disconnected(device_mxid)
        logger.debug(f'Device {product_name}: thread stopped.')

    def __poll_device(self, device: OakCamera) -> None:
        """
        Poll the device for new data. This method is called in a separate thread.

        :param device: The device to poll.
        """
        while self.running:
            if not device.poll():
                return

            time.sleep(0.0025)

    def __device_stats_reporting(self, device_mxid: str) -> None:
        """
        Report device info and stats every 30 seconds.

        :param device_mxid: The mxid of the device to report info/stats for.
        """
        dai_device = self.__devices[device_mxid].device
        state = self.__device_states[device_mxid]
        while self.running:
            try:
                device_info = get_device_details(dai_device, state)
                device_stats = get_device_performance_metrics(dai_device)

                robothub_core.AGENT.publish_device_info(device_info)
                robothub_core.AGENT.publish_device_stats(device_stats)
            except Exception as e:
                product_name = self.__device_product_names[dai_device.getMxId()]
                logger.debug(f'Device {product_name}: could not report info/stats with error: {e}.')

            self.wait(30)

    def __connect(self, device_mxid: str) -> None:
        """
        Connect to the device. This method is called in a separate thread.

        :param device_mxid: The mxid of the device to connect to.
        """
        start_time = time.time()
        give_up_time = start_time + 30

        self.__device_states[device_mxid] = robothub_core.DeviceState.CONNECTING
        product_name = self.__device_product_names[device_mxid]
        while time.time() < give_up_time and self.running:
            logger.debug(f'Device {product_name}: remaining time to connect - {give_up_time - time.time()} seconds.')
            try:
                oak = OakCamera(device_mxid)
                self.__devices[device_mxid] = oak
                self.__device_states[device_mxid] = robothub_core.DeviceState.CONNECTED
                logger.debug(f'Device {product_name}: successfully connected.')
                return
            except Exception as e:
                # If device can't be connected to on first try, wait 5 seconds and try again.
                logger.debug(f'Device {product_name}: error while trying to connect - {e}.')
                self.wait(5)

        logger.info(f'Device {product_name}: could not manage to connect within 30s timeout.')
        self.__devices[device_mxid] = None
        self.__device_states[device_mxid] = robothub_core.DeviceState.DISCONNECTED
        return

    def __close_device(self, mxid: str):
        """
        Close the device gracefully. If the device is not running, this method does nothing.

        :param mxid: The mxid of the device to close.
        """
        if self.__devices.get(mxid) is None or not self.__devices[mxid].running():
            return

        self.__devices[mxid].__exit__(1, 2, 3)
        self.__devices[mxid] = None
        product_name = self.__device_product_names[mxid]
        logger.info(f'Device {product_name}: closed gracefully.')

    def get_device(self, mxid: str) -> Optional[OakCamera]:
        """
        Get a device by its mxid. If the device is not running, this method returns None.

        :param mxid: The mxid of the device to get.
        :return: The device with the given mxid.
        """
        return self.__devices.get(mxid)

    def restart_device(self, mxid: str):
        """
        Restart the specified device.

        :param mxid: The mxid of the device to restart.
        """
        if mxid not in self.__devices:
            logger.warning(f"Device {mxid} not found for restart.")
            return

        with self.__manage_condition:
            self.__close_device(mxid)
            self.__manage_condition.notify_all()  # Notify the manage_device thread of the restart
