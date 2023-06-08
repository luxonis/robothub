from typing import Callable


class Component:
    def __init__(self):
        self.callbacks = []

    def add_callback(self, callback: Callable) -> None:
        self.callbacks.append(callback)
