import logging as log
from pathlib import Path
from typing import Dict, Any, Union

import robothub_oak

__all__ = [
    'try_or_default',
    'set_logging_level',
    '_process_kwargs',
    '_get_methods_by_class',
    '_convert_to_enum',
    'set_replay_path'
]


def try_or_default(func, default=None):
    try:
        return func()
    except:
        return default


def set_logging_level(level):
    if level != 'DEBUG' or level != log.DEBUG:
        log.basicConfig(format='%(levelname)s | %(message)s')
    else:
        log.basicConfig()

    log.getLogger().setLevel(level)


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


def _convert_to_enum(name: Any, cls: Any) -> Any:
    """
    Get an enum by name.

    :param cls: The enum class.
    :param name: The name of the enum.
    :return: The enum.
    """
    if isinstance(name, cls):
        return name

    try:
        return getattr(cls, name)
    except AttributeError:
        return None


def set_replay_path(path: Union[Path, str]) -> None:
    """
    Use the replay functionality to use a recorded video instead of the live camera feed.

    :param path: Path to the video file or folder.
    """
    robothub_oak.REPLAY_PATH = str(path)
