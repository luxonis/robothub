import os

try:
    import blobconverter

    blobconverter.set_defaults(silent=True)
except ImportError:
    blobconverter = None

from .device import *
from .hub_camera import *
from .manager import *
from .utils import set_replay_path

__version__ = '1.4.1'

REPLAY_PATH = os.environ.get('RH_OAK_REPLAY_PATH', None)
