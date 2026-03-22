import logging
import threading
from datetime import datetime

import pytz
from flask import current_app
from rq import Queue

logger = logging.getLogger(__name__)

_lock = threading.Lock()


class TaskQueueManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with _lock:
                # Double-checked locking: re-test after acquiring the lock
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialize()
                    cls._instance = instance
        return cls._instance

    def _initialize(self):
        self.queue = Queue(connection=current_app.config["SESSION_REDIS"])
        self.redis_worker_timeout = current_app.config["REDIS_WORKER_TIMEOUT"]
        logger.info("TaskQueueManager initialized with Redis connection.")

    def enqueue_task(self, task_name: str, *args, timeout=None, **kwargs):
        """
        Queue a task for async execution via RQ.

        :param task_name: Dotted path to the function (e.g. ‘app.tasks.process’).
        :param timeout: Max execution time in seconds. Defaults to REDIS_WORKER_TIMEOUT.
        """
        if timeout is None:
            timeout = self.redis_worker_timeout

        logger.info(
            "Enqueueing task ‘%s’ (args=%s, kwargs=%s, timeout=%s, ts=%s)",
            task_name,
            args,
            kwargs,
            timeout,
            datetime.now(pytz.utc).isoformat(),
        )

        self.queue.enqueue(task_name, *args, **kwargs, job_timeout=timeout)
