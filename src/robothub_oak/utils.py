import logging

from typing import Dict, Any

__all__ = [
    'try_or_default',
    'set_logging_level',
    '_process_kwargs',
    '_get_methods_by_class'
]


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


def _get_methods_by_class(cls: Any) -> list:
    """
    Get all methods of a class that are not private.

    :param cls: The class to get the methods from.
    :return: A list of methods.
    """
    return [x for x in dir(cls) if callable(getattr(cls, x)) and not x.startswith('_')]
