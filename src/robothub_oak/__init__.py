import os

from robothub_oak.application import *
from robothub_oak.live_view import *
from robothub_oak.utils import setup_logger

try:
    import blobconverter

    # Suppress blobconverter logs
    blobconverter.set_defaults(silent=True)
except ImportError:
    pass

__version__ = '2.1.0'

REPLAY_PATH = os.environ.get('RH_OAK_REPLAY_PATH', None) or os.environ.get('RH_REPLAY_PATH', None)

# Setup logging for the module
setup_logger(__name__)
