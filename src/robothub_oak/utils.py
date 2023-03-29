import logging

__all__ = ['try_or_default', 'set_logging_level']


def try_or_default(func, default=None):
    try:
        return func()
    except:
        return default


def set_logging_level(level):
    logging.basicConfig()
    logging.getLogger().setLevel(level)
