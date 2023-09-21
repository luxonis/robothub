import contextlib
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from threading import Thread
from typing import Optional

import robothub_core
from depthai_sdk import OakCamera

from robothub.utils import get_device_details, get_device_performance_metrics

__all__ = ["BaseApplication"]

logger = logging.getLogger(__name__)

REPLAY_PATH = os.environ.get('RH_OAK_REPLAY_PATH', None) or os.environ.get('RH_REPLAY_PATH', None)


class BaseApplication(robothub_core.RobotHubApplication, ABC):
    """
    This class acts as the main entry point for the user, managing a single device, creating pipelines,
    and polling the device for new data. Derived classes must implement the `setup_pipeline` method.

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

        self.config = robothub_core.CONFIGURATION

        self.__rh_device: Optional[robothub_core.RobotHubDevice] = None
        self.__device_mxid: Optional[str] = None
        self.__device_product_name: Optional[str] = None
        self.__device_state: Optional[robothub_core.DeviceState] = None
        self.__device_thread: Optional[Thread] = None
        self.__device_stop_event = threading.Event()
        self.__device: Optional[OakCamera] = None

    def on_start(self) -> None:
        if len(robothub_core.DEVICES) == 0:
            logger.info("No assigned devices.")
            self.stop_event.set()
            return
        if len(robothub_core.DEVICES) > 1:
            logger.warning("More than one device assigned, only the first one will be used.")

        self.__rh_device = robothub_core.DEVICES[0]
        self.__device_mxid = self.__rh_device.oak["serialNumber"]
        self.__device_product_name = (
            self.__rh_device.oak.get("name", None)
            or self.__rh_device.oak.get("productName", None)
            or self.__device_mxid
        )
        self.__device_state = robothub_core.DeviceState.DISCONNECTED

        self.__device_thread = Thread(
            target=self.__manage_device,
            name=f"manage_{self.__device_mxid}",
            daemon=False,
        )
        self.__device_thread.start()

    def start_execution(self) -> None:
        self.stop_event.wait()  # Keep main thread alive

    def on_stop(self) -> None:
        """
        Called when the application is stopped. Registered as atexit handler.
        """
        # Device thread must close the device
        self.__device_stop_event.set()
        with contextlib.suppress(Exception):
            self.__device_thread.join()
            logger.debug(f"Device thread {self.__device_product_name}: stopped.")
        robothub_core.STREAMS.destroy_all_streams()

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

    def on_device_disconnected(self) -> None:
        """
        Called when a camera is disconnected. Opposite of on_device_connected.
        """
        pass

    def __manage_device(self) -> None:
        """
        Handle the life cycle of the device.
        """
        logger.debug(f"Device {self.__device_product_name}: management thread started.")

        try:
            while self.running:
                self.__manage_device_inner()
        finally:
            # Make sure device is closed
            self.__close_device()
            logger.debug(f"Device {self.__device_product_name}: thread stopped.")

    def __manage_device_inner(self) -> None:
        # Connect device
        self.__device_stop_event.clear()
        self.__connect()
        if self.__device is None:
            # Wait 30 seconds before trying to connect again
            self.wait(30)
            return

        # Start device
        logger.debug(f"Device {self.__device_product_name}: creating pipeline...")
        self.setup_pipeline(oak=self.__device)
        self.__device.start(blocking=False)
        self.on_device_connected(self.__device)
        logger.info(f"Device {self.__device_product_name}: started successfully.")

        # Start threads for polling and reporting
        polling_thread = Thread(
            target=self.__poll_device,
            daemon=False,
            name=f"poll_{self.__device_mxid}",
        )
        reporting_thread = Thread(
            target=self.__report_info_and_stats,
            daemon=False,
            name=f"reporting_{self.__device_mxid}",
        )
        polling_thread.start()
        reporting_thread.start()

        # Wait for device to stop
        polling_thread.join()
        reporting_thread.join()

        # Close device
        self.__close_device()
        self.on_device_disconnected()

    def __poll_device(self) -> None:
        """
        Poll the device for new data. This method is called in a separate thread.
        """
        try:
            while self.running and not self.__device_stop_event.is_set():
                self.__device.poll()
                if not self.__device.running():
                    break
                time.sleep(0.0025)
        finally:
            self.__device_stop_event.set()

    def __report_info_and_stats(self) -> None:
        """
        Report device info and stats every 30 seconds.
        """
        product_name = self.__device_product_name
        while self.running and not self.__device_stop_event.is_set():
            try:
                device_info = get_device_details(self.__device.device, self.__device_state)
                robothub_core.AGENT.publish_device_info(device_info)
            except Exception as e:
                logger.debug(f"Device {product_name}: could not report info with error: {e}.")

            try:
                device_stats = get_device_performance_metrics(self.__device.device)
                robothub_core.AGENT.publish_device_stats(device_stats)
            except Exception as e:
                logger.debug(f"Device {product_name}: could not report stats with error: {e}.")

            self.__device_stop_event.wait(30)

    def __connect(self) -> None:
        """
        Connect to the device. This method is called in a separate thread.
        """
        give_up_time = time.monotonic() + 30

        self.__device_state = robothub_core.DeviceState.CONNECTING
        product_name = self.__device_product_name
        while self.running and time.monotonic() < give_up_time:
            logger.debug(
                f"Device {product_name}: remaining time to connect - {give_up_time - time.monotonic()} seconds."
            )
            try:
                oak = OakCamera(self.__device_mxid, replay=REPLAY_PATH)
            except Exception as e:
                # If device can't be connected to on first try, wait 5 seconds and try again.
                logger.debug(
                    f"Device {product_name}: error while trying to connect - {e}."
                )
                self.wait(5)
            else:
                self.__device = oak
                self.__device_state = robothub_core.DeviceState.CONNECTED
                logger.debug(f"Device {product_name}: successfully connected.")
                return

        logger.info(
            f"Device {product_name}: could not manage to connect within 30s timeout."
        )
        self.__device_state = robothub_core.DeviceState.DISCONNECTED
        return

    def __close_device(self):
        """
        Close the device gracefully. If the device is not running, this method does nothing.
        """
        with contextlib.suppress(Exception):
            self.__device.__exit__(1, 2, 3)
            logger.info(f"Device {self.__device_product_name}: closed gracefully.")
        self.__device = None

    def get_device(self) -> Optional[OakCamera]:
        """
        Get a device by its mxid. If the device is not running, this method returns None.
        :return: The device or None if the device is not running.
        """
        return self.__device

    def restart_device(self):
        """
        Restart the device.
        """
        if not self.__device:
            logger.warning(f"Device is not initialized and cannot be restarted.")
            return

        self.__device_stop_event.set()
