from abc import ABC, abstractmethod


class BaseEventConsumer(ABC):

    @abstractmethod
    def receive_message(self):
        pass

    @abstractmethod
    def delete_message(
        self,
        receipt_handle: str
    ):
        pass

    @abstractmethod
    def change_message_visibility(
        self,
        receipt_handle: str,
        visibility_timeout: int,
    ) -> None:
        pass