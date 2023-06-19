from abc import abstractmethod, ABC
from typing import Callable, List, Dict, Any


class Component(ABC):
    def __init__(self):
        self.callbacks: List[Dict[str, Any]] = []
        self._valid_output_types: List[str] = []
        self.set_valid_output_types()

    def add_callback(self, callback: Callable, output_type: str = 'main') -> None:
        """
        Adds a callback to the component.

        :param callback: The callback function.
        :param output_type: The type of the output to add the callback to. Defaults to 'main'.
        """
        self.callbacks.append({
            'callback': callback,
            'output_type': output_type
        })

    def validate_output_type(self, output_type: str) -> bool:
        """
        Validates the output of the component.

        :param output_type: The output type to validate.
        :return: True if the output type is valid, False otherwise.
        """
        return output_type in self._valid_output_types

    @abstractmethod
    def set_valid_output_types(self) -> None:
        """
        Sets the valid output types of the component.
        """
        pass

    def get_valid_output_types(self) -> List[str]:
        """
        Gets the valid output types of the component.

        :return: A list of valid output types.
        """
        return self._valid_output_types
