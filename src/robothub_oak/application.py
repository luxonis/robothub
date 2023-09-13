import atexit
import logging
import signal
import threading
import time

from abc import ABC, abstractmethod
from threading import Thread
from typing import Optional

import robothub_core
from depthai_sdk import OakCamera

from robothub_oak import REPLAY_PATH
from robothub_oak.utils import get_device_performance_metrics, get_device_details

__all__ = ["BaseApplication"]

logger = logging.getLogger(__name__)


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
        self.__device: Optional[OakCamera] = None
        self.__device_thread: Optional[Thread] = None

        atexit.register(self.__cleanup)
        signal.signal(signal.SIGUSR1, self.__cleanup)

        self.__manage_event = threading.Event()
        self.__report_event = threading.Event()

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

    def __cleanup(self, *args, **kwargs) -> None:
        """
        Called when the application is stopped. Registered as atexit handler.
        """
        # Device thread must close the device
        self.stop_event.set()
        self.__manage_event.set()
        self.__report_event.set()

        self.__device_thread.join()

    def __manage_device(self) -> None:
        """
        Handle the life cycle of the device.
        """
        logger.debug(f"Device {self.__device_product_name}: management thread started.")

        while self.running:
            # if device is not connected
            if self.__device is None or not self.__device.running():
                # Make sure it is properly closed in case it disconnected during runtime
                self.__close_device()
                self.on_device_disconnected()

                # Connect to the device
                self.__connect()

                # If device is connected
                if self.__device:
                    logger.debug(f"Device {self.__device_product_name}: creating pipeline...")

                    self.setup_pipeline(oak=self.__device)
                    self.__device.start(blocking=False)
                    self.on_device_connected(self.__device)

                    logger.info(f"Device {self.__device_product_name}: started successfully.")

                    self.__manage_event.clear()
                    self.__report_event.clear()

                    # Threads for polling and reporting
                    polling_thread = Thread(
                        target=self.__poll_device,
                        daemon=True,
                        name=f"poll_{self.__device_mxid}",
                    )
                    polling_thread.start()

                    reporting_thread = Thread(
                        target=self.__device_stats_reporting,
                        daemon=False,
                        name=f"stats_reporting_{self.__device_mxid}",
                    )
                    reporting_thread.start()
                else:
                    self.__manage_event.wait(25)

            self.__manage_event.wait(5)

        # Make sure device is closed
        self.__close_device()
        self.on_device_disconnected()
        logger.debug(f"Device {self.__device_product_name}: thread stopped.")

    def __poll_device(self) -> None:
        """
        Poll the device for new data. This method is called in a separate thread.
        """
        while self.running and not self.__manage_event.is_set():
            if not self.__device.poll():
                return

            time.sleep(0.0025)

    def __device_stats_reporting(self) -> None:
        """
        Report device info and stats every 30 seconds.
        """
        dai_device = self.__device.device
        state = self.__device_state
        while self.running and not self.__report_event.is_set():
            if self.__device is None or not self.__device.running():
                return

            try:
                device_info = get_device_details(dai_device, state)
                device_stats = get_device_performance_metrics(dai_device)

                robothub_core.AGENT.publish_device_info(device_info)
                robothub_core.AGENT.publish_device_stats(device_stats)
            except Exception as e:
                product_name = self.__device_product_name
                logger.debug(f"Device {product_name}: could not report info/stats with error: {e}.")

            self.__report_event.wait(30)

    def __connect(self) -> None:
        """
        Connect to the device. This method is called in a separate thread.
        """
        give_up_time = time.time() + 30

        self.__device_state = robothub_core.DeviceState.CONNECTING
        product_name = self.__device_product_name
        while time.time() < give_up_time and self.running:
            logger.debug(
                f"Device {product_name}: remaining time to connect - {give_up_time - time.time()} seconds."
            )
            try:
                oak = OakCamera(self.__device_mxid, replay=REPLAY_PATH if REPLAY_PATH else None)
                self.__device = oak
                self.__device_state = robothub_core.DeviceState.CONNECTED
                logger.debug(f"Device {product_name}: successfully connected.")
                return
            except Exception as e:
                # If device can't be connected to on first try, wait 5 seconds and try again.
                logger.debug(f"Device {product_name}: error while trying to connect - {e}.")
                self.wait(5)

        logger.info(f"Device {product_name}: could not manage to connect within 30s timeout.")
        self.__device = None
        self.__device_state = robothub_core.DeviceState.DISCONNECTED
        return

    def __close_device(self):
        """
        Close the device gracefully. If the device is not running, this method does nothing.
        """
        if self.__device is None or not self.__device.running():
            return

        self.__device.__exit__(1, 2, 3)
        self.__device = None
        product_name = self.__device_product_name
        logger.info(f"Device {product_name}: closed gracefully.")

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

        self.__close_device()
        self.__report_event.set()
        self.__manage_event.set()
