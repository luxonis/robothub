import robothub.decorators
from robothub.application import *
from robothub.events import *
from robothub.frame_buffer import *
from robothub.live_view import *
from robothub.replay import *
from robothub.utils import setup_logger

try:
    import blobconverter

    # Suppress blobconverter logs
    blobconverter.set_defaults(silent=True)
except ImportError:
    pass

# Import symbols from robothub_core and make them available under the robothub namespace
try:
    import robothub_core as robothub
except ImportError:
    import robothub.robothub_core_wrapper as robothub

__version__ = "2.6.0"

# Setup logging for the module
# setup_logger(__name__)
