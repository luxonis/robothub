import os

try:
    import blobconverter

    blobconverter.set_defaults(silent=True)
except:
    pass

from .device import *
from .hub_camera import *
from .manager import *

__version__ = '1.4.0'

REPLAY_PATH = os.environ.get('RH_OAK_REPLAY_PATH', None)
