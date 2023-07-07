"""Defines various global variables."""

import os
from robothub._exceptions import RobotHubFatalException
from robothub.device import RobotHubDevice
import json

__all__ = ['TEAM_ID', 'APP_INSTANCE_ID', 'APP_VERSION', 'ROBOT_ID', 'STORAGE_DIR', 'PUBLIC_FILES_DIR', 'CONFIGURATION', 'DEVICES']

TEAM_ID = os.environ.get('ROBOTHUB_TEAM_ID')
"""ID of RobotHub team Robot running the App belongs to."""
if TEAM_ID == None:
    raise RobotHubFatalException('Environment variable "ROBOTHUB_TEAM_ID" not set')

APP_VERSION = os.environ.get('ROBOTHUB_APP_VERSION')
"""Version of the source the App was installed with."""
if APP_VERSION == None:
    raise RobotHubFatalException('Environment variable "ROBOTHUB_APP_VERSION" not set')

APP_INSTANCE_ID = os.environ.get('ROBOTHUB_ROBOT_APP_ID')
"""ID of instance of the App on current Robot. Not the ID of the App."""
if APP_INSTANCE_ID == None:
    raise RobotHubFatalException('Environment variable "ROBOTHUB_ROBOT_APP_ID" not set')

ROBOT_ID = os.environ.get('ROBOTHUB_ROBOT_ID')
"""ID of Robot running the App."""
if ROBOT_ID == None:
    raise RobotHubFatalException('Environment variable "ROBOTHUB_ROBOT_ID" not set')

STORAGE_DIR = '/storage'
"""Storage directory for Events and other files, can be used by the user"""
PUBLIC_FILES_DIR = '/public'
"""Storage directory intended for public assets"""

#APP_ID: str # TODO
#"""ID of the App"""

with open('/config/config.json') as f:
    CONFIGURATION = json.load(f)
    """Current configuration values of the App, loaded at App startup. Configuration structure is defined in C{robotapp.toml}"""
with open('/config/devices.json') as f:
    _devices_json = json.load(f)
    DEVICES = []
    """List of devices assigned to the App."""
    for _device in _devices_json:
      DEVICES.append(RobotHubDevice('oak', _device))
