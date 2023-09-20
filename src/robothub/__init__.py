from robothub.application import *
from robothub.live_view import *
from robothub.utils import setup_logger

try:
    import blobconverter

    # Suppress blobconverter logs
    blobconverter.set_defaults(silent=True)
except ImportError:
    pass

__version__ = '2.2.0'

# Setup logging for the module
setup_logger(__name__)
