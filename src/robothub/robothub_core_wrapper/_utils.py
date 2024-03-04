import threading


def count_threads(include_main: bool = True, include_daemon: bool = True):
    count = 0
    for thread in threading.enumerate():
        if include_daemon or not thread.daemon:
            count += 1
    if not include_main:
        count -= 1
    return count
