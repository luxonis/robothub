import logging

from abc import ABC, abstractmethod
from enum import Enum
from robothub_core import AGENT
from robothub_core import RobothubApplication as RhApp
from threading import Thread
from time import monotonic
from typing import Optional
from uuid import uuid4

__all__ = ["WatchDog", "AgentResponse"]

logger = logging.getLogger(__name__)


class AgentResponse(Enum):
    RESTART = "restart"
    NOTIFY = "notify"


# send_health_check_init(health_check_frequency) -> message = {'what': 'wish', 'type': "health_check", 'body': {"frequency": frequency: float, "action": "restart" or "notify", "id_: "unique uuid", "description": "user defined string"}}
# message = {'what': 'notification', 'type': "health_check", 'body': {"frequency": frequency: float, "action": "restart" or "notify"}}
# destroy watch dog: message = {'what': 'wish', 'type': "health_check_destroy", 'body': {"id_: "unique_uuid"}}


class WatchDog(ABC):
    __active_watch_dogs = set()

    @classmethod
    def create(cls, interval_seconds: float, description: str, agent_response: AgentResponse = AgentResponse.RESTART) -> "WatchDogChild":
        new_watch_dog = WatchDogChild(interval_seconds=interval_seconds, description=description, agent_response=agent_response)
        cls.__active_watch_dogs.add(new_watch_dog)
        return new_watch_dog

    @classmethod
    def destroy_all(cls):
        for watch_dog in cls.__active_watch_dogs:
            watch_dog.destroy()
        cls.__active_watch_dogs.clear()

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def ping(self):
        pass

    @abstractmethod
    def destroy(self):
        pass


class WatchDogChild(WatchDog):
    __id: str
    __interval: float
    __last_ping: Optional[float]

    def __init__(self, interval_seconds: float, description: str, agent_response: AgentResponse = AgentResponse.RESTART) -> None:
        self.__agent_response = agent_response
        self.__description = description
        self.__id = str(uuid4())
        self.__interval = interval_seconds
        self.__last_ping = None

    def start(self) -> None:
        AGENT.send_watch_dog_init(interval=self.__interval, action=self.__agent_response.value, id_=self.__id, description=self.__description)
        self.__last_ping = monotonic()
        Thread(target=self.__run).start()

    def __run(self):
        while RhApp.running():
            RhApp.wait(self.__interval)
            now = monotonic()
            if now - self.__last_ping < self.__interval:
                AGENT.send_watch_dog_ping()
                self.__last_ping = now

    def ping(self):
        assert self.__last_ping is not None, f"WatchDog has to be started! Use the 'start()' method first!"
        self.__last_ping = monotonic()

    def destroy(self):
        AGENT.send_watch_dog_destroy(self.__id)
