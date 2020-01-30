from background_task_manager.runner import BackgroundTaskRunner


class AbstractCommunicator(BackgroundTaskRunner):
    def __init__(self, use_asyncio=None):
        BackgroundTaskRunner.__init__(self, use_asyncio=use_asyncio)
        self._interpreter = None
        self.send_queue = []

    @property
    def interpreter(self):
        return self._interpreter

    @interpreter.setter
    def interpreter(self, interpreter):
        self._interpreter = interpreter
