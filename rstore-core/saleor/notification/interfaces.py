from abc import ABCMeta, abstractmethod


class PushManager(metaclass=ABCMeta):

    @abstractmethod
    def send_to_all(self, payload: dict):
        pass

    @abstractmethod
    def send_to_segment(self, payload: dict):
        pass

    @abstractmethod
    def send_to_target_audience(self, payload: dict):
        pass
