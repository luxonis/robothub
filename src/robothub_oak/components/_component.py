from typing import Callable, List


class Component:
    def __init__(self):
        self.callbacks: List[Callable] = []

    def add_callback(self, callback: Callable) -> None:
        self.callbacks.append(callback)
