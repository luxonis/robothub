
import logging

from enum import Enum
from robothub_core import AGENT
from robothub_core import RobothubApplication as RhApp
from threading import Thread
from time import monotonic
from typing import Callable, Optional


__all__ = ["WatchDog"]

logger = logging.getLogger(__name__)


class Status(Enum):
    OK = 0
    ERROR = 1


class WatchDog:

    status = Status.OK

    __id: str
    __interval: float
    __last_ping: Optional[float]

    def __init__(self, id_: str, interval_seconds: float) -> None:
        self.__id = id_
        self.__interval = interval_seconds
        self.__last_ping = None

    def start(self) -> None:
        self.__last_ping = monotonic()
        Thread(target=self.__run).start()

    def __run(self):
        while RhApp.running():
            RhApp.wait(self.__interval)
            now = monotonic()
            if now - self.__last_ping > self.__interval:
                self.status = Status.ERROR

    def ping(self):
        assert self.__last_ping is not None, f"WatchDog has to be started! Use the 'start()' method first!"
        self.__last_ping = monotonic()

    @classmethod
    def status_is_ok(cls) -> bool:
        return cls.status == Status.OK
