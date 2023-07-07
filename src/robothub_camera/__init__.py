import os

try:
    import blobconverter

    blobconverter.set_defaults(silent=True)
except:
    pass

__version__ = '1.4.0'

REPLAY_PATH = os.environ.get('RH_OAK_REPLAY_PATH', None)
