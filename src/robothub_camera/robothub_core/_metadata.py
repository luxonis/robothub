from dataclasses import dataclass

__all__ = ['DeviceMetadata', 'OverlayMetadata']


@dataclass
class DeviceMetadata:
    name: str
    mxid: str


@dataclass
class OverlayMetadata:
    pass
