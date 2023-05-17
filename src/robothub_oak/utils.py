import logging

__all__ = ['try_or_default', 'set_logging_level', '_process_kwargs']

from typing import Dict, Any


def try_or_default(func, default=None):
    try:
        return func()
    except:
        return default


def set_logging_level(level):
    logging.basicConfig()
    logging.getLogger().setLevel(level)


def _process_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Process the kwargs and remove all None values."""
    kwargs.pop('self')
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    return kwargs
