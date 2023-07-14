import os

from robothub_oak.application import *
from robothub_oak.live_view import *

try:
    import blobconverter

    blobconverter.set_defaults(silent=True)
except:
    pass

__version__ = '1.0.0'

REPLAY_PATH = os.environ.get('RH_OAK_REPLAY_PATH', None) or os.environ.get('RH_REPLAY_PATH', None)
