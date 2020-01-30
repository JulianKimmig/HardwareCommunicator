def delete_on_send(item, communicator_target):
    del item


class SendItem:
    def __init__(self, data, on_send=None):
        self.data = data
        if on_send is None:
            on_send = delete_on_send
        self._on_send = on_send

    def sended(self, communicator_target):
        if self in communicator_target.send_queue:
            communicator_target.send_queue.remove(self)
            self._on_send(self, communicator_target)

    def __str__(self):
        return f"{self.__class__.__name__}({self.data})"

    def __repr__(self):
        return f"{self.__class__.__name__}({self.data})"


class AbstractInterpreter:
    pass
