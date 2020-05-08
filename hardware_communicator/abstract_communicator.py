import functools
import logging
import random
import threading
import time

from json_dict import JsonDict


class BackgroundTask:
    def __init__(
        self, id, method, delay, name=None, max_callings=None, initial_delay=0
    ):
        self._run_thread: threading.Thread = None
        if name is None:
            rff = method
            while isinstance(rff, functools.partial):
                rff = rff.func
            name = rff.__name__
        self.name = name
        self.remain_callings = max_callings
        self.delay = delay
        self.method = method
        self.id = id
        self._last_run = time.time() + initial_delay
        self.running = True

    def check_for_run(self, t=None):
        if self.remain_callings == 0:
            self.stop()
            return None

        if self.delay is None:
            return self.run(t)

        if t is None:
            t = time.time()
        if t >= self._last_run + self.delay:
            return self.run(t)

    def run(self, t=None):
        if t is None:
            t = time.time()
        self._last_run = t
        if self.remain_callings:
            self.remain_callings -= 1
        return self.method()

    def stop(self):
        self.running = False
        try:
            self._run_thread.join(timeout=self.delay + 0.2)
        except:
            pass

    def __repr__(self):
        return f"{self.name}({self.delay},{self.remain_callings},{self.id})"

    def start(self, background_sleep_time=None):
        if background_sleep_time is None:
            background_sleep_time = 0.01
        if self._run_thread:
            self.stop()

        def runner():
            while self.running:
                self.check_for_run()
                time.sleep(background_sleep_time)

        self._run_thread = threading.Thread(target=runner, daemon=True)
        self._run_thread.start()


class ThreadedBackgroundTaskManager:
    def __init__(self, background_sleep_time=1):
        self.background_sleep_time = background_sleep_time
        self._background_tasks = {}

    def stop(self):
        for id in self._background_tasks.copy():
            self.stop_task(id)
        self._running = False

    def has_running_tasks(self):
        return any([t.running for t in self._background_tasks.values()])

    def stop_task(self, id):
        if id in self._background_tasks:
            try:
                self._background_tasks[id].stop()
            except:
                pass
            try:
                del self._background_tasks[id]
            except:
                pass

    def register_background_task(
        self, method, minimum_call_delay=None, max_callings=None, name=None, delay=0
    ):
        task_id = random.randint(1, 10 ** 6)
        while task_id in self._background_tasks:
            task_id = random.randint(1, 10 ** 6)
        if name is None:
            rff = method
            while isinstance(rff, functools.partial):
                rff = rff.func
            name = rff.__name__
        self._background_tasks[task_id] = BackgroundTask(
            id=task_id,
            method=method,
            delay=minimum_call_delay,
            max_callings=max_callings,
            name=name,
            initial_delay=delay,
        )
        self._background_tasks[task_id].start(self.background_sleep_time)
        return task_id


class AbstractCommunicator(ThreadedBackgroundTaskManager):
    def __init__(self, interpreter, on_connect=None, config=None, **kwargs):
        super().__init__(**kwargs)
        self._interpreter = None
        self.interpreter = interpreter
        if config:
            self.config = config
        else:
            self.config = JsonDict()

        self.send_queue = []
        self.connection_checks = []
        self.connected = False
        if not hasattr(self, "logger"):
            self.logger = logging.getLogger(self.__class__.__name__)
        if not hasattr(self, "on_connect") or on_connect is not None:
            self.on_connect = on_connect

    @property
    def interpreter(self):
        return self._interpreter

    @interpreter.setter
    def interpreter(self, interpreter):
        interpreter.communicator = self
        self._interpreter = interpreter

    def add_connection_check(self, function):
        self.connection_checks.append(function)

    def try_to_connect(self, **kwargs):
        return None

    def get_connection_info(self):
        return {}
