import contextlib
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from threading import Thread
from typing import Optional, Union

import depthai
try:
    import robothub_core
except ImportError:
    import robothub.robothub_core_wrapper as robothub_core
from depthai_sdk import OakCamera
from robothub.replay import ReplayCamera
from robothub.utils import get_device_details, get_device_performance_metrics

__all__ = ["AGENT", "app_is_running", "BaseDepthAIApplication", "BaseSDKApplication", "LOCAL_DEV", "TEAM_ID", "APP_INSTANCE_ID", "APP_VERSION",
           "ROBOT_ID", "STORAGE_DIR", "PUBLIC_FILES_DIR", "COMMUNICATOR", "CONFIGURATION", "DEVICES", "STREAMS", "StreamHandle", "EVENTS",
           "DEVICE_MXID", "wait"]

logger = logging.getLogger(__name__)

REPLAY_PATH = os.environ.get("RH_OAK_REPLAY_PATH", None) or os.environ.get("RH_REPLAY_PATH", None)

AGENT = robothub_core.AGENT
APP_INSTANCE_ID = robothub_core.APP_INSTANCE_ID
APP_VERSION = robothub_core.APP_VERSION
COMMUNICATOR = robothub_core.COMMUNICATOR
CONFIGURATION = robothub_core.CONFIGURATION
DEVICES = robothub_core.DEVICES
EVENTS = robothub_core.EVENTS
PUBLIC_FILES_DIR = robothub_core.PUBLIC_FILES_DIR
ROBOT_ID = robothub_core.ROBOT_ID
STORAGE_DIR = robothub_core.STORAGE_DIR
StreamHandle = robothub_core.StreamHandle
STREAMS = robothub_core.STREAMS
TEAM_ID = robothub_core.TEAM_ID

app_is_running = robothub_core.app_is_running
DeviceState = robothub_core.DeviceState
RobotHubDevice = robothub_core.RobotHubDevice
wait = robothub_core.wait
DEVICE_MXID = "unknown"

# this needs to be in sync with globals.py from robothub_core wrapper
LOCAL_DEV = APP_INSTANCE_ID == "ROBOTHUB_ROBOT_APP_ID" and APP_VERSION == "ROBOTHUB_APP_VERSION"


class BaseApplication(robothub_core.RobotHubApplication, ABC):

    def __init__(self):
        robothub_core.RobotHubApplication.__init__(self)
        ABC.__init__(self)

        self.config = CONFIGURATION

        self.__rh_device: Optional[robothub_core.RobotHubDevice] = None
        self._device_mxid: Optional[str] = None
        self._device_ip: Optional[str] = None
        self._device_product_name: Optional[str] = None
        self.__device_state: Optional[robothub_core.DeviceState] = None
        self.__device_thread: Optional[Thread] = None
        self._device_stop_event = threading.Event()
        self._device: Optional[Union[OakCamera, depthai.Device]] = None

    @property
    def device_is_running(self) -> bool:
        return not self._device_stop_event.is_set()

    def on_start(self) -> None:
        global DEVICE_MXID
        if len(DEVICES) == 0:
            logger.info("No assigned devices.")
            self.stop_event.set()
            return
        if len(DEVICES) > 1:
            logger.warning("More than one device assigned, only the first one will be used.")

        self.__rh_device = DEVICES[0]
        self._device_mxid = self.__rh_device.oak["serialNumber"]
        DEVICE_MXID = self._device_mxid
        self._device_ip = self.__rh_device.oak["ipAddress"]
        
        self._device_product_name = (
            self.__rh_device.oak.get("name", None)
            or self.__rh_device.oak.get("productName", None)
            or self._device_mxid)

        self.__device_state = robothub_core.DeviceState.DISCONNECTED
        self.__report_device_info()

        # run __manage_device in the main thread when developing locally - enables the usa of cv2.imshow()
        if LOCAL_DEV is True:
            return

        self.__device_thread = Thread(
            target=self.__manage_device,
            name=f"manage_{self._device_mxid}",
            daemon=False,
        )
        self.__device_thread.start()

    def start_execution(self):
        if LOCAL_DEV is True:
            self.__manage_device()
        else:
            robothub_core.wait()

    def on_stop(self) -> None:
        """
        Called when the application is stopped.
        """
        logger.info(f"Application is terminating...")
        # Device thread must close the device
        self._device_stop_event.set()
        with contextlib.suppress(Exception):
            self.__device_thread.join()
            logger.info(f"Device thread {self._device_product_name}: stopped.")
        robothub_core.STREAMS.destroy_all_streams()

    def __manage_device(self) -> None:
        """
        Handle the life cycle of the device.
        """
        logger.info(f"Device {self._device_product_name}: management thread started.")

        try:
            while app_is_running():
                self._manage_device_inner()
        finally:
            # Make sure device is closed
            self._close_device()
            logger.info(f"Device {self._device_product_name}: thread stopped.")

    def _report_info_and_stats(self) -> None:
        """
        Report device info and stats every 30 seconds.
        """
        while app_is_running() and self.device_is_running:
            self.__report_device_info()
            self.__report_device_stats()
            self._device_stop_event.wait(30)

    def __report_device_info(self) -> None:
        try:
            device_info = get_device_details(self._get_dai_device(), self.__device_state)
            robothub_core.AGENT.publish_device_info(device_info)
        except Exception as e:
            logger.error(f"Device {self._device_product_name}: could not report info with error: {e}.")

    def __report_device_stats(self) -> None:
        try:
            device_stats = get_device_performance_metrics(self._get_dai_device())
            robothub_core.AGENT.publish_device_stats(device_stats)
        except Exception as e:
            logger.error(f"Device {self._device_product_name}: could not report stats with error: {e}.")

    def _connect(self) -> None:
        """
        Connect to the device. This method is called in a separate thread.
        """
        give_up_time = time.monotonic() + 30

        self.__device_state = robothub_core.DeviceState.CONNECTING
        self.__report_device_info()
        product_name = self._device_product_name
        logger.info(f"Establishing connection with Device {product_name}...")
        while self.running and time.monotonic() < give_up_time:
            logger.debug(
                f"Device {product_name}: remaining time to connect - {give_up_time - time.monotonic()} seconds."
            )
            try:
                self._device = self._acquire_device()
                                    
            except Exception as e:
                # If device can't be connected to on first try, wait 5 seconds and try again.
                logger.error(f"Device {product_name}: error while trying to connect - {e}.")
                self.wait(5)
            else:
                self.__device_state = robothub_core.DeviceState.CONNECTED
                self.__report_device_info()
                logger.info(f"Device {product_name}: successfully connected.")
                return

        logger.error(f"Device {product_name}: could not manage to connect within 30s timeout.")
        self.__device_state = robothub_core.DeviceState.DISCONNECTED
        self.__report_device_info()
        return

    def _close_device(self):
        """
        Close the device gracefully. If the device is not running, this method does nothing.
        """
        with contextlib.suppress(Exception):
            self._device.__exit__(1, 2, 3)
            logger.info(f"Device {self._device_product_name}: closed gracefully.")
        self._device = None

    def get_device(self) -> Optional[Union[OakCamera, depthai.Device]]:
        """
        Get a device by its mxid. If the device is not running, this method returns None.

        :return: The device or None if the device is not running.
        """
        return self._device

    def restart_device(self):
        """
        Restart the device.
        """
        if not self._device:
            logger.warning("Device is not initialized and cannot be restarted.")
            return

        self._device_stop_event.set()

    @abstractmethod
    def _get_dai_device(self) -> depthai.Device:
        pass

    @abstractmethod
    def _manage_device_inner(self):
        pass

    @abstractmethod
    def _acquire_device(self):
        pass


class BaseDepthAIApplication(BaseApplication):
    def _manage_device_inner(self) -> None:
        self._device_stop_event.clear()
        self._connect()
        if self._device is None:
            # Wait 30 seconds before trying to connect again
            self.wait(30)
            return
        logger.info(f"Device {self._device_product_name}: creating Pipeline...")
        self.pipeline = self.setup_pipeline()
        assert self.pipeline is not None, f"setup_pipeline() must return a valid depthai.Pipeline object but returned {self.pipeline}."
        logger.info(f"Device {self._device_product_name}: Pipeline created...")

        self._device.startPipeline(self.pipeline)
        self._start_replay()

        if LOCAL_DEV is True:
            self.manage_device(self._device)
        else:
            # Start threads for user loop and reporting
            device_thread = Thread(
                target=self.manage_device,
                args=(self._device,),
                daemon=False,
                name=f"loop_{self._device_mxid}",
            )
            reporting_thread = Thread(
                target=self._report_info_and_stats,
                daemon=False,
                name=f"reporting_{self._device_mxid}",
            )
            device_thread.start()
            reporting_thread.start()

            # Wait for device to stop
            device_thread.join()
            reporting_thread.join()

        # Close device
        self._close_device()

    def _start_replay(self):
        for replay in ReplayCamera.replay_camera_instances:
            replay.start_polling(self._device)

    def _acquire_device(self) -> depthai.Device:
        return depthai.Device(depthai.DeviceInfo(self._device_ip or self._device_mxid))

    def _get_dai_device(self) -> depthai.Device:
        return self._device

    @abstractmethod
    def setup_pipeline(self) -> depthai.Pipeline:
        pass

    @abstractmethod
    def manage_device(self, device: depthai.Device):
        pass


class BaseSDKApplication(BaseApplication):
    """
    This class acts as the main entry point for the SDK user, managing a single device, creating pipelines,
    and polling the device for new data. Derived classes must implement the `setup_pipeline` method.
    """

    def _manage_device_inner(self) -> None:
        # Connect device
        self._device_stop_event.clear()
        self._connect()
        if self._device is None:
            # Wait 30 seconds before trying to connect again
            self.wait(30)
            return

        # Start device
        logger.info(f"Device {self._device_product_name}: creating pipeline...")
        self.setup_pipeline(oak=self._device)
        self._device.start(blocking=False)
        self.on_device_connected(self._device)
        logger.info(f"Device {self._device_product_name}: started successfully.")

        # Start threads for polling and reporting
        polling_thread = Thread(
            target=self.__poll_device,
            daemon=False,
            name=f"poll_{self._device_mxid}",
        )
        reporting_thread = Thread(
            target=self._report_info_and_stats,
            daemon=False,
            name=f"reporting_{self._device_mxid}",
        )
        polling_thread.start()
        reporting_thread.start()

        # Wait for device to stop
        polling_thread.join()
        reporting_thread.join()

        # Close device
        self._close_device()
        self.on_device_disconnected()

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

    def __poll_device(self) -> None:
        """
        Poll the device for new data. This method is called in a separate thread.
        """
        try:
            while self.running and not self._device_stop_event.is_set():
                self._device.poll()
                if not self._device.running():
                    break
                time.sleep(0.0025)
        finally:
            self._device_stop_event.set()
            
    def _acquire_device(self) -> OakCamera:
        return OakCamera(self._device_ip or self._device_mxid,
                         replay=REPLAY_PATH)

    def _get_dai_device(self) -> depthai.Device:
        return self._device.device
