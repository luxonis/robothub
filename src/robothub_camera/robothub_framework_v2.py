
import depthai as dai
import logging as log

from depthai_sdk import OakCamera
from depthai_sdk.components import Component, CameraComponent, NNComponent, StereoComponent, IMUComponent
from depthai_sdk.components.camera_helper import sensorResolutions
from depthai_sdk.oak_outputs.xout.xout_h26x import XoutH26x
from depthai_sdk.oak_outputs.xout.xout_base import StreamXout
from robothub_core import RobotHubApplication, DEVICES, RobotHubDevice, CONFIGURATION, STREAMS
from robothub_interface import LiveView, send_robothub_image_event

from abc import ABC, abstractmethod
from threading import Thread
from time import time
from typing import Dict, List, Optional


class RobothubCameraApplication(RobotHubApplication, ABC):
    
    def __init__(self):
        super().__init__()
        
        self.__polling_threads = []
        self.__reporting_threads = []
        self.__camera_threads = []
        self.__oaks: Dict[str, Optional[OakCamera]] = {}

        self.config = CONFIGURATION

    def on_start(self) -> None:
        for device in DEVICES:
            device_thread = Thread(target=self.__manage_device, kwargs={"device": device}, name=f"connection_{device.oak['serialNumber']}")
            device_thread.start()
            self.__camera_threads.append(device_thread)
            self.__oaks[device.oak["serialNumber"]] = None

    @abstractmethod
    def on_application_start(self) -> None:
        pass
            
    @abstractmethod
    def create_pipeline(self, oak: OakCamera):
        pass

    def after_pipeline_starts(self, oak: OakCamera):
        pass

    def __manage_device(self, device: RobotHubDevice):
        """Handle the life cycle of one device."""
        
        device_mxid = device.oak['serialNumber']
        log.info(f"Camera: {device_mxid} thread started...")
        log.info(f"Creating camera data processors for {device_mxid}...")
        # must be created only once
        self.on_application_start()
        while self.running:
            # if device is not connected
            if self.__oaks[device_mxid] is None or not self.__oaks[device_mxid].running():
                # make sure it is properly closed in case it disconnected during runtime
                self.__close_oak(device_mxid)
                log.info(f"Device is not connected. Trying to connect...")
                self.__connect(device_mxid)
                # device did connect
                if self.__oaks[device_mxid] is not None:
                    log.info(f"Creating pipeline for {device_mxid}...")
                    self.create_pipeline(oak=self.__oaks[device_mxid])
                    self.__oaks[device_mxid].start(blocking=False)
                    log.info(f"Pipeline/Camera: {device_mxid} started...")
                    # optionally implemented by the user
                    self.after_pipeline_starts(oak=self.__oaks[device_mxid])

                    # get data to the callback which user defined
                    polling_thread = Thread(target=self._polling, daemon=True, name=f"polling_{device_mxid}")
                    polling_thread.start()
                    self.__polling_threads.append(polling_thread)

                    reporting_thread = Thread(target=self.__device_stats_reporting, daemon=True, name=f"device_stats_reporting_{device_mxid}")
                    reporting_thread.start()
                    self.__reporting_threads.append(reporting_thread)
                # device did not connect
                else:
                    log.info(f"Device is disconnected. I will try to reconnect in 25 seconds...")
                    self.wait(25.)
            self.wait(5.)
        self.__close_oak(mxid=device_mxid)
        log.info(f"Camera {device_mxid} thread ended...")

    def _polling(self):
        pass
    
    def __device_stats_reporting(self):
        pass
    
    def __connect(self, mxid: str) -> None:
        """If connect is succesfull -> self.oak = OakCamera, else self.oak = None"""

        self.wait(2.)
        log.info(f"Trying to connect to {mxid}")
        start_time = time()
        give_up_time = start_time + 30
        while time() < give_up_time and self.running:
            log.info(f"Remaining time to connect: {give_up_time - time()} seconds")
            try:
                oak = OakCamera(mxid)
                self.__oaks[mxid] = oak
                log.info(f'Connected device "{mxid}"')
                return
            except Exception as e:
                # If device can't be connected to on first try, wait 5 seconds and try again.
                log.info(f"Error while trying to connect {mxid}: {e}")
                self.wait(2.5)
        # connection failed
        log.info(f'Device "{mxid}" could not be connected within 30s timeout')
        self.__oaks[mxid] = None
        return
    
    def __close_oak(self, mxid: str):
        """Close device gracefully and reset oak to None."""

        if self.__oaks[mxid] is not None:
            log.info(f"Closing OAK...")
            self.__oaks[mxid].__exit__(1, 2, 3)
            self.__oaks[mxid] = None

    def on_stop(self) -> None:
        pass
