"""Defines base classes for handling of devices and their states."""

from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

__all__ = ['RobotHubDevice', 'DeviceState']

@dataclass
class RobotHubDevice(ABC):
    """RobotHub device base class."""
    type: str # currently only `oak`
    """String denoting type of the device, allowed values: ["oak"]"""
    oak: Dict[str, Any]
    """Dictionary containing various information about the device"""


class DeviceState(Enum):
    """Possible states of a device connected to the Agent."""
    # WIP
    CONNECTED = 'connected'
    """Agent is actively communicating with the device. In the case of DepthAI devices, this means a pipeline is running on the device."""
    DISCONNECTED = 'disconnected'
    """Agent is not actively communicating with the device. Either device is disconnected or no App is running on it."""
    CONNECTING = 'connecting'
    """Agent is connecting to the device. Occurs when an App is initializing on the device, but full communication is not yet going on."""
    UNKNOWN = 'unknown'
    """Agent is trying to obtain info about device state. Occurs when Agent is starting up."""