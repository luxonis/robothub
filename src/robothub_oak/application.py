import logging as log
import time
from abc import ABC, abstractmethod
from threading import Thread
from typing import Dict, Optional

import robothub_core
from depthai_sdk import OakCamera

from robothub_oak.utils import get_device_performance_metrics, get_device_details

__all__ = ['Application']


class Application(robothub_core.RobotHubApplication, ABC):
    def __init__(self):
        robothub_core.RobotHubApplication.__init__(self)
        ABC.__init__(self)

        self.__polling_threads = []
        self.__reporting_threads = []
        self.__camera_threads = []
        self.__devices: Dict[str, Optional[OakCamera]] = {}
        self.__device_states: Dict[str, robothub_core.DeviceState] = {}

        self.config = robothub_core.CONFIGURATION

    def on_start(self) -> None:
        for device in robothub_core.DEVICES:
            device_mxid = device.oak['serialNumber']
            self.__devices[device_mxid] = None
            self.__device_states[device_mxid] = robothub_core.DeviceState.DISCONNECTED

            device_thread = Thread(target=self.__manage_device,
                                   kwargs={'device': device},
                                   name=f'connection_{device_mxid}')
            device_thread.start()
            self.__camera_threads.append(device_thread)

    def on_stop(self) -> None:
        for device_mxid in self.__devices:
            self.__close_oak(device_mxid)

        for thread in self.__camera_threads:
            thread.join()

        for thread in self.__polling_threads:
            thread.join()

        for thread in self.__reporting_threads:
            thread.join()

        self.__camera_threads.clear()
        self.__polling_threads.clear()
        self.__reporting_threads.clear()
        self.__devices.clear()
        self.__device_states.clear()

    def start_execution(self) -> None:
        self.stop_event.wait()  # Keep main thread alive

    @abstractmethod
    def setup_pipeline(self, device: OakCamera):
        pass

    def __manage_device(self, device: robothub_core.RobotHubDevice):
        """Handle the life cycle of one device."""
        device_mxid = device.oak['serialNumber']
        log.debug(f'Device {device_mxid}: management thread started.')

        while self.running:
            # if device is not connected
            if self.__devices[device_mxid] is None or not self.__devices[device_mxid].running():
                # Make sure it is properly closed in case it disconnected during runtime
                self.__close_oak(device_mxid)

                # Connect to the device
                self.__connect(device_mxid)

                # If device is connected
                if self.__devices[device_mxid]:
                    log.debug(f'Device {device_mxid}: creating pipeline...')

                    self.setup_pipeline(device=self.__devices[device_mxid])
                    self.__devices[device_mxid].start(blocking=False)
                    log.info(f'Device {device_mxid}: started successfully.')

                    # Threads for polling and reporting
                    polling_thread = Thread(target=self.__poll_device,
                                            args=(self.__devices[device_mxid],),
                                            daemon=True,
                                            name=f'poll_{device_mxid}')
                    polling_thread.start()
                    self.__polling_threads.append(polling_thread)

                    reporting_thread = Thread(target=self.__device_stats_reporting,
                                              args=(device_mxid,),
                                              daemon=True,
                                              name=f'stats_reporting_{device_mxid}')
                    reporting_thread.start()
                    self.__reporting_threads.append(reporting_thread)
                else:
                    self.wait(25)

            self.wait(5)

        self.__close_oak(mxid=device_mxid)
        log.debug(f'Device {device_mxid}: thread stopped.')

    def __poll_device(self, device: OakCamera):
        while self.running:
            if not device.poll():
                return

            time.sleep(0.0025)

    def __device_stats_reporting(self, device_mxid: str):
        dai_device = self.__devices[device_mxid].device
        state = self.__device_states[device_mxid]
        while self.running:
            try:
                device_info = get_device_details(dai_device, state)
                device_stats = get_device_performance_metrics(dai_device)

                robothub_core.AGENT.publish_device_info(device_info)
                robothub_core.AGENT.publish_device_stats(device_stats)
            except Exception as e:
                log.debug(f'Device {dai_device.getMxId()}: could not report info/stats with error: {e}.')

            self.wait(30)

    def __connect(self, device_mxid: str) -> None:
        """If connect is succesfull -> self.oak = OakCamera, else self.oak = None"""
        start_time = time.time()
        give_up_time = start_time + 30

        self.__device_states[device_mxid] = robothub_core.DeviceState.CONNECTING

        while time.time() < give_up_time and self.running:
            log.debug(f'Device {device_mxid}: remaining time to connect - {give_up_time - time.time()} seconds.')
            try:
                oak = OakCamera(device_mxid)
                self.__devices[device_mxid] = oak
                self.__device_states[device_mxid] = robothub_core.DeviceState.CONNECTED
                log.debug(f'Device {device_mxid}: successfully connected.')
                return
            except Exception as e:
                # If device can't be connected to on first try, wait 5 seconds and try again.
                log.debug(f'Device {device_mxid}: error while trying to connect - {e}.')
                self.wait(5)

        log.info(f'Device {device_mxid}: could not manage to connect within 30s timeout.')
        self.__devices[device_mxid] = None
        self.__device_states[device_mxid] = robothub_core.DeviceState.DISCONNECTED
        return

    def __close_oak(self, mxid: str):
        """Close device gracefully and reset oak to None."""
        if self.__devices[mxid]:
            self.__devices[mxid].__exit__(1, 2, 3)
            self.__devices[mxid] = None
            log.info(f'Device {mxid}: closed gracefully.')
