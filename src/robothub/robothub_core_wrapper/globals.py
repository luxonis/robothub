"""Defines various global variables."""

import json
import logging as log
import os
import toml

import depthai as dai
from robothub.robothub_core_wrapper._exceptions import RobotHubFatalException
from robothub.robothub_core_wrapper.device import RobotHubDevice

__all__ = ['TEAM_ID', 'APP_INSTANCE_ID', 'APP_VERSION', 'ROBOT_ID', 'STORAGE_DIR', 'PUBLIC_FILES_DIR', 'CONFIGURATION', 'DEVICES',
           '_load_configuration']

TEAM_ID = os.environ.get('ROBOTHUB_TEAM_ID', 'ROBOTHUB_TEAM_ID')
"""ID of RobotHub team Robot running the App belongs to."""
if TEAM_ID is None:
    raise RobotHubFatalException('Environment variable "ROBOTHUB_TEAM_ID" not set')

APP_VERSION = os.environ.get('ROBOTHUB_APP_VERSION', 'ROBOTHUB_APP_VERSION')
"""Version of the source the App was installed with."""
if APP_VERSION is None:
    raise RobotHubFatalException('Environment variable "ROBOTHUB_APP_VERSION" not set')

APP_INSTANCE_ID = os.environ.get('ROBOTHUB_ROBOT_APP_ID', 'ROBOTHUB_ROBOT_APP_ID')
"""ID of instance of the App on current Robot. Not the ID of the App."""
if APP_INSTANCE_ID is None:
    raise RobotHubFatalException('Environment variable "ROBOTHUB_ROBOT_APP_ID" not set')

ROBOT_ID = os.environ.get('ROBOTHUB_ROBOT_ID', 'ROBOTHUB_ROBOT_ID')
"""ID of Robot running the App."""
if ROBOT_ID is None:
    raise RobotHubFatalException('Environment variable "ROBOTHUB_ROBOT_ID" not set')

ROBOTHUB_CONFIG_PATH = os.environ.get('ROBOTHUB_CONFIG_PATH', 'robotapp.toml')
LOCAL_CONFIG_PATH = os.environ.get('ROBOTHUB_LOCAL_CONFIG_PATH', 'local_config.json')

STORAGE_DIR = '/storage'
"""Storage directory for Events and other files, can be used by the user"""
PUBLIC_FILES_DIR = '/public'
"""Storage directory intended for public assets"""

CONFIGURATION = {}


def _load_configuration():
    global CONFIGURATION
    """Current configuration values of the App, loaded at App startup. Configuration structure is defined in C{robotapp.toml}"""
    try:
        with open(ROBOTHUB_CONFIG_PATH, "r") as file:
            rh_config = toml.load(file)
    except FileNotFoundError:
        log.critical(f"Configuration file 'robotapp.toml' not found in the root dir.")
        rh_defaults = {}
    else:
        rh_defaults = {}
        for config in rh_config["configuration"]:
            if "key" in config:
                if config.get("field") == "choice":
                    options = config["options"]
                    for option in options:
                        if "default" in option and option["default"] is True:
                            rh_defaults[config["key"]] = option["key"]
                else:
                    rh_defaults[config["key"]] = config["initial_value"]

    try:
        with open(LOCAL_CONFIG_PATH, "r") as file:
            local_config = json.load(file)
    except FileNotFoundError:
        log.info(f"Local configuration file not found, using default configuration from robotapp.toml\n"
                 f"Local configuration is expected to be in the root dir with name 'local_config.json'.\n"
                 f"You can change the path to the local configuration file by setting the environment variable 'ROBOTHUB_LOCAL_CONFIG_PATH'")
        local_config = {}
    for key, value in local_config.items():
        if key not in rh_defaults:
            log.warning(f"Configuration key {key} not found in local configuration file. Ignoring...")
        else:
            rh_defaults[key] = value
    CONFIGURATION.update(rh_defaults)


_load_configuration()

DEVICES = []
available_devices = dai.Device.getAllAvailableDevices()
for device_info in available_devices:
    device_info: dai.DeviceInfo
    device_info_as_dict = {"ipAddress": device_info.name,
                           "name": device_info.mxid,
                           "productName": None,
                           "serialNumber": device_info.mxid
                           }
    DEVICES.append(RobotHubDevice('oak', device_info_as_dict))
