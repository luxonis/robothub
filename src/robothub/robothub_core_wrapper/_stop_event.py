import threading

STOP_EVENT = threading.Event()
"""Event which is set when App is stopped by Agent."""


def app_is_running() -> bool:
    """
    Returns True if App is running, False otherwise.
    """
    return not STOP_EVENT.is_set()


def wait(timeout: float | int | None = None) -> bool:
    """
    Invoking this function will sleep current thread until
    either B{timeout} seconds have passed or App is stopped.
    """
    return STOP_EVENT.wait(timeout)
