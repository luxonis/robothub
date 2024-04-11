"""
Contains the base class for your application.
"""

import logging as log
import os
import signal
import sys
import threading
from abc import ABC, abstractmethod

from robothub.robothub_core_wrapper._stop_event import (STOP_EVENT,
                                                        app_is_running, wait)
from robothub.robothub_core_wrapper._utils import count_threads
from robothub.robothub_core_wrapper.client import AGENT
from robothub.robothub_core_wrapper.communicator import COMMUNICATOR
from robothub.robothub_core_wrapper.events import EVENTS, UploadedEvent
from robothub.robothub_core_wrapper.streams import STREAMS

__all__ = ['RobotHubApplication', 'threading']


class RobotHubApplication(ABC):
    """
    Base class for your RobotHub App.
    """
    def __init__(self) -> None:
        """Constructor"""
        signal.signal(signal.SIGINT, self._handle_SIGINT_signal)
        threading.excepthook = self._default_thread_excepthook
        self.stop_event = STOP_EVENT
        """Deprecated, will be removed. Use C{app_is_running} or C{wait} functions instead."""
        self._exit_code = 0
        self._is_stopped = False
        self.warn_timeout = None  # threading.Timer
        self.kill_timeout = None  # threading.Timer

    @property
    def running(self) -> bool:
        """
        Deprecated, will be removed. Use C{app_is_running} instead.

        Set to C{True} at startup. Is set to C{False} when either App is stopped by Agent or it excepts.

        @return: True if App is running, False otherwise. 
        """
        return app_is_running()

    def wait(self, time: float | int | None = None) -> None:
        """
        Deprecated, will be removed. Use C{wait} instead.

        Invoking this function will sleep current thread for B{time} seconds.

        If C{self.running -> False}, returns immediately. If App is stopped midway through C{self.wait}, likewise returns immediately.

        Should be preferred over C{time.sleep} in all use cases, as C{time.sleep} will not be interrupted if App is stopped, often causing unexpected behaviour.

        @param time: Time to sleep for, given in seconds. Negative values are interpreted as 0.
        @type time: float | int
        """
        wait(time)

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
        Optional. Is called when an Event is uploaded to cloud. UploadedEvent argument contains information about the uploaded Event.

        Is not called if Event is rejected by Agent

        @param event: Object containing information about the uploaded event.
        @type event: L{UploadedEvent}
        """
        pass

    def on_configuration_changed(self, configuration_changes: dict) -> None:
        """
        Is called when the Agent receives a new configuration. New configuration is loaded into the CONFIGURATION variable.
        A dictionary containing configuration changes [:param: configuration_changes] is provided so that user can decide proper behavior when this
        method is overriden.
        Default behavior is app restart. Override this method if you want to change the behavior.

        @param configuration_changes: Dictionary containing configuration changes.
        @type configuration_changes: dict
        """
        log.info(f"Configuration changed. Changed values: {configuration_changes}")
        log.info(f"App Configuration changed. Restarting app. If you want to change the behavior, override `on_configuration_changed` method.")
        self.restart()

    def on_assigned_devices_changed(self):
        """
        Is called when Devices assigned to the app have changed.
        """
        log.info(f"Devices assigned to the app changed. Restarting App")
        self.restart()

    def stop(self) -> None:
        """
        Stops the App.
        """
        log.debug("App requested to stop")
        os.kill(os.getpid(), signal.SIGINT)

    def restart(self) -> None:
        """
        Restarts the App. This blocks execution until Agent stops the App. App is then started.
        """
        log.info(f"restart is not available in local environment. Ignoring restart request.")

    def restart_host(self) -> None:
        """
        Requests the Agent to restart Host. Blocks execution until request is resolved.
        """
        log.info(f"restart_host is not available in local environment. Ignoring restart request.")

    def shutdown_host(self) -> None:
        """
        Requests the Agent to shutdown Host. Blocks execution until request is resolved.
        """
        log.info(f"shutdown_host is not available in local environment. Ignoring shutdown request")

    def _default_thread_excepthook(self, args) -> None:
        """Redefining threading.excepthook to this will throw whenever a thread excepts."""
        log.exception("Uncaught Thread Exception occured, printing traceback and Exiting!")
        self._exit_code = 1
        os.kill(os.getpid(), signal.SIGINT)

    def _on_start_timeout(self, kill=False) -> None:
        if self.running:
            if kill:
                log.error('`on_start` has not returned within 5 minutes, stopping app!')
                self._exit_code = 50
                os.kill(os.getpid(), signal.SIGINT)
            else:
                log.warning('`on_start` has not returned within 30 seconds, app will be stopped in 5 minutes!')

    def _start_timers(self):
        if self.warn_timeout is not None or self.kill_timeout is not None:
            self._dispose_timers()
        self.warn_timeout = threading.Timer(30, self._on_start_timeout)
        self.kill_timeout = threading.Timer(5 * 60, lambda: self._on_start_timeout(kill=True))
        self.warn_timeout.start()
        self.kill_timeout.start()

    def _dispose_timers(self):
        if self.warn_timeout is not None:
            self.warn_timeout.cancel()
        if self.kill_timeout is not None:
            self.kill_timeout.cancel()

    def run(self) -> None:
        """Launch script uses this method to start the App."""
        self._bind_globals()

        try:
            self._run_inner()
        except SystemExit:
            pass

        try:
            self.on_stop()
        except Exception:
            log.exception("Exception occured during `on_stop`")
            self._exit_code = 49
        AGENT._shutdown()

        non_daemon_threads_count = count_threads(include_daemon=False)
        log.debug(f"Exit code: {self._exit_code}")
        if non_daemon_threads_count > 1:
            log.warning(f"App exited with {non_daemon_threads_count} non-daemon threads still running")
            os._exit(self._exit_code)
        sys.exit(self._exit_code)

    def _run(self) -> None:
        self.run()

    def _run_inner(self) -> None:
        # Try to call on_start, if it fails, exit with code 47
        try:
            self._start_timers()
            self.on_start()
            self._dispose_timers()
            AGENT._send_start_notification()
        except Exception:
            log.exception("App crashed during initialization")
            self._exit_code = 47
            self._stop()

        # Try to call start_execution, if it fails, exit with code 48
        log.info('Starting execution')
        try:
            self.start_execution()
        except Exception:
            log.exception("App crashed during execution")
            self._exit_code = 48
            self._stop()

        # If execution finished, wait for stop event
        log.debug("App finished execution, waiting for stop event")
        wait()
        self._stop()

    def _stop(self):
        """Stops the app"""
        if self._is_stopped:
            log.debug("Method _stop is called twice, ignoring")
            return
        self._is_stopped = True
        STOP_EVENT.set()
        self._dispose_timers()
        sys.exit()

    def _handle_SIGINT_signal(self, unused_signum, unused_frame) -> None:
        """Called when SIGINT is received"""
        log.debug("SIGINT is received")
        self._stop()

    def _bind_globals(self) -> None:
        """Give global variables references to each other as needed while preventing circular imports"""
        AGENT._bind_app_(self)
        EVENTS._bind_agent_(AGENT)
        STREAMS._bind_agent_(AGENT)

        AGENT._bind_streams_(STREAMS)

        COMMUNICATOR._bind_agent_(AGENT)
        AGENT._bind_communicator_(COMMUNICATOR)
