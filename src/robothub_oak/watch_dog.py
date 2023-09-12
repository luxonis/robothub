import logging

from abc import ABC, abstractmethod
from enum import Enum
from robothub_core import AGENT
from robothub_core import RobothubApplication as RhApp
from threading import Thread, Event
from time import monotonic
from typing import Optional
from uuid import uuid4

__all__ = ["WatchDog", "AgentResponse"]

logger = logging.getLogger(__name__)


class WatchdogNotStartedError(Exception):
    def __init__(self):
        message = "WatchDog has to be started! Use the 'start()' method first!"
        super().__init__(message)


class AgentResponse(Enum):
    RESTART_APP = "restart"
    SEND_EMAIL_NOTIFICATION = "notify"


# send_health_check_init(health_check_frequency) -> message = {'what': 'wish', 'type': "health_check", 'body': {"frequency": frequency: float, "action": "restart" or "notify", "id_: "unique uuid", "description": "user defined string"}}
# message = {'what': 'notification', 'type': "health_check", 'body': {"frequency": frequency: float, "action": "restart" or "notify"}}
# destroy watch dog: message = {'what': 'wish', 'type': "health_check_destroy", 'body': {"id_: "unique_uuid"}}


class WatchDog:
    __active_watch_dogs = set()

    def __init__(self, heartbeat_interval_seconds: float, description: str, agent_response: AgentResponse = AgentResponse.RESTART_APP) -> None:
        self.__agent_response = agent_response
        self.__description = description
        self.__id = str(uuid4())
        self.__interval = heartbeat_interval_seconds
        self.__last_ping = None
        self.__stop_event = Event()

    def start(self) -> None:
        AGENT.send_watch_dog_init(interval=self.__interval, action=self.__agent_response.value, id_=self.__id, description=self.__description)
        self.__last_ping = monotonic()
        Thread(target=self.__run).start()

    def __run(self):
        while self.__is_active():
            if self.__ping_received_in_time():
                AGENT.send_watch_dog_ping()
            RhApp.wait(self.__interval)
        self.destroy()

    def __is_active(self) -> bool:
        return RhApp.app_is_running() and not self.__stop_event.is_set()

    def __ping_received_in_time(self):
        return monotonic() - self.__last_ping < self.__interval

    def ping(self):
        if self.__last_ping is None:
            raise WatchdogNotStartedError
        self.__last_ping = monotonic()

    def destroy(self):
        if not self.__stop_event.is_set():
            self.__stop_event.set()
            # we want to notify AGENT only once
            AGENT.send_watch_dog_destroy(self.__id)

    @classmethod
    def create_instance(cls, interval_seconds: float, description: str, agent_response: AgentResponse = AgentResponse.RESTART_APP) -> "WatchDog":
        new_watch_dog = WatchDog(heartbeat_interval_seconds=interval_seconds, description=description, agent_response=agent_response)
        cls.__active_watch_dogs.add(new_watch_dog)
        return new_watch_dog

    @classmethod
    def destroy_all(cls):
        for watch_dog in cls.__active_watch_dogs:
            watch_dog.destroy()
        cls.__active_watch_dogs.clear()
