import os

from robothub_oak.application import *
from robothub_oak.live_view import *
from robothub_oak.utils import set_logging_level

try:
    import blobconverter

    blobconverter.set_defaults(silent=True)
except:
    pass

__version__ = '2.1.0'

REPLAY_PATH = os.environ.get('RH_OAK_REPLAY_PATH', None) or os.environ.get('RH_REPLAY_PATH', None)

set_logging_level('INFO')
