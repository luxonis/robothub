"""
Contains the base class for your application.
"""

from abc import ABC, abstractmethod

import atexit
import signal
from typing import Any, Dict, Callable, List
import traceback
import os
import sys

import threading
import time

from robothub.communicator import COMMUNICATOR
from robothub.client import AGENT
from robothub.develop import DEVELOP
from robothub.events import UploadedEvent, EVENTS
from robothub.streams import STREAMS


import logging as log
log.basicConfig(format = '%(levelname)s | %(funcName)s:%(lineno)s => %(message)s', level = log.INFO)

__all__ = ['RobotHubApplication', 'threading']


class RobotHubApplication(ABC):
    """
    Base class for your RobotHub App.
    """
    def __init__(self) -> None:
        """Constructor"""
        log.debug(f'Initializing base App class')
        signal.signal(signal.SIGUSR1, self._signal_handler)
        threading.excepthook = self._default_thread_excepthook
        self.stop_event = threading.Event()
        """Deprecated, will be removed. threading.Event() which is set when App is stopped by Agent or excepts."""
        log.debug(f'Done Initializing base App class')

    @property
    def running(self) -> bool:
        """Set to C{True} at startup. Is set to C{False} when either App is stopped by Agent or it excepts.

        @return: True if App is running, False otherwise. 
        """
        return not self.stop_event.is_set()

    def wait(self, time: float | int) -> None:
        """
        Invoking this function will sleep current thread for B{time} seconds.

        If C{self.running -> False}, returns immediately. If App is stopped midway through C{self.wait}, likewise returns immediately.

        Should be preferred over C{time.sleep} in all use cases, as C{time.sleep} will not be interrupted if App is stopped, often causing unexpected behaviour.

        @param time: Time to sleep for, given in seconds. Negative values are interpreted as 0.
        @type time: float | int
        """
        if not isinstance(time, (float, int)):
            raise TypeError(f'"time" argument must be either float or int, but is type "{type(time)}"')
        self.stop_event.wait(timeout = time)

    @abstractmethod
    def on_start(self) -> None:
        """
        Entrypoint of the App. Must be defined by the user.

        """
        pass

    def start_execution(self) -> None:
        """
        Optional method, is executed after L{on_start()} returns.

        Can be used as a second entrypoint to the App.
        """
        pass

    def on_stop(self) -> None:
        """
        Method for cleanup of threads/processes, is called when:
            - App is stopped by Agent (e.g. due to a request to Stop from the Cloud)
            - App stops on its own - for example by calling C{exit()}
            - App throws an uncaught exception

        Should be used to quickly and gracefully stop all execution. Not defining this method properly, such as not joining all threads that were started in C{self.on_start()} often results in undefined behaviour.
        Not called when C{os._exit()} is called.
        """
        pass

    def on_event_uploaded(self, event: UploadedEvent) -> None:
        """
        Optional. Is called on UploadedEvent objects which contain information about the uploaded Event.

        Is not called if Event is rejected by Agent

        @param event: Object containing information about the uploaded event.
        @type event: L{UploadedEvent}
        """
        pass

    def restart(self) -> None:
        """
        Restarts the App. This blocks execution until Agent stops the App. App is then started.
        """
        # TODO test this
        AGENT._restart_app(blocking=True)

    def restart_host(self) -> None:
        """
        Requests the Agent to restart Host. Blocks execution until request is resolved.
        """
        # TODO test this
        AGENT._restart_host(blocking=True)

    def shutdown_host(self) -> None:
        """
        Requests the Agent to shutdown Host. Blocks execution until request is resolved.
        """
        # TODO test this
        AGENT._shutdown_host(blocking=True)

    def _default_thread_excepthook(self, args) -> None:
        """Redefining threading.excepthook to this will throw whenever a thread excepts."""
        log.error(f"Uncaught Thread Exception occured, printing traceback and Exiting!")
        print(traceback.format_exc())
        self._stop(1)

    def _run(self) -> None:
        """Launch script uses this method to start the App."""
        self._bind_globals()
        try:
            self.on_start()
            AGENT._send_start_notification()
        except:
            log.error(f'App crashed during initialization')
            print(traceback.format_exc())
            self._stop(47)
        if not self.stop_event.is_set():
            log.debug('Starting execution')
            atexit.register(self._stop_handler)
            self.start_execution()

    def _stop(self, exc: int):
        """Stops the app"""
        try:
            atexit.unregister(self._stop_handler)
        except BaseException as e:
            log.debug(f'Couldn\'t unregister stop handler because {e}')

        self.stop_event.set()
        self.on_stop()

        while COMMUNICATOR._timeout_async_thread.is_alive():
            time.sleep(0.001)

        try:
            AGENT._shutdown()
        except BaseException as e:
            log.debug(f'Agent shutdown excepted with {e}')

        if len(threading.enumerate()) > 1:
            exit(exc)
        else:
            # Only main thread is "running" at this point
            if threading.main_thread().is_alive():
                os._exit(exc)

    def _signal_handler(self, unused_signum, unused_frame) -> None:
        """Called when SIGUSR1 is received"""
        log.debug('Signal handler called')
        self._stop(0)

    def _stop_handler(self) -> None:
        """Called at exit"""
        log.debug('Crash handler called')
        self._stop(1)

    def _bind_globals(self) -> None:
        """Give global variables references to each other as needed while preventing circular imports"""
        AGENT._bind_app_(self)
        EVENTS._bind_app_(self, AGENT)
        STREAMS._bind_app_(self, AGENT)
        DEVELOP._bind_app_(self)

        AGENT._bind_streams_(STREAMS)

        COMMUNICATOR._bind_agent_(AGENT)
        COMMUNICATOR._bind_app_(self)
        AGENT._bind_communicator_(COMMUNICATOR)

