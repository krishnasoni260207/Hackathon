from __future__ import annotations

import asyncio
import logging
import threading
import uuid

logger = logging.getLogger(__name__)


class StaleRequestError(Exception):
    """Raised when an operation is attempted on an obsolete or interrupted request."""


class InterruptionController:
    """Keeps track of the currently active request and manages cancellation of stale work."""

    def __init__(self) -> None:
        self._current_request_id: str | None = None
        self._tasks: dict[str, set[asyncio.Task]] = {}
        self._lock = threading.Lock()

    def start_request(self) -> str:
        """Create a new request and make it the active request.
        
        Any previously active request is marked stale and its running tasks are cancelled.
        """
        request_id = uuid.uuid4().hex

        with self._lock:
            old_request_id = self._current_request_id
            self._current_request_id = request_id
            tasks_to_cancel = list(self._tasks.get(old_request_id, set())) if old_request_id else []
            self._tasks[request_id] = set()

        for task in tasks_to_cancel:
            if not task.done():
                logger.info("Cancelling task %s for superseded request %s", task.get_name(), old_request_id)
                task.cancel()

        return request_id

    def interrupt(self, request_id: str | None = None) -> None:
        """Invalidate the currently active request and cancel all its in-flight tasks.
        
        Args:
            request_id: If provided, only interrupt if this request is currently active.
                       If None, unconditionally interrupt the active request.
        """
        tasks_to_cancel: list[asyncio.Task] = []

        with self._lock:
            if request_id is not None and self._current_request_id != request_id:
                return  # Request was already superseded or interrupted

            target_id = self._current_request_id
            self._current_request_id = None
            if target_id and target_id in self._tasks:
                tasks_to_cancel = list(self._tasks[target_id])

        for task in tasks_to_cancel:
            if not task.done():
                logger.info("Cancelling task %s on interruption of request %s", task.get_name(), target_id)
                task.cancel()

    def register_task(self, request_id: str, task: asyncio.Task) -> None:
        """Register an in-flight asyncio task with a request ID for cancellation upon interruption."""
        with self._lock:
            if self._current_request_id != request_id:
                # Request is already stale — cancel immediately
                task.cancel()
                return

            if request_id not in self._tasks:
                self._tasks[request_id] = set()
            self._tasks[request_id].add(task)

        task.add_done_callback(lambda t: self._cleanup_task(request_id, t))

    def _cleanup_task(self, request_id: str, task: asyncio.Task) -> None:
        with self._lock:
            if request_id in self._tasks:
                self._tasks[request_id].discard(task)
                if not self._tasks[request_id] and self._current_request_id != request_id:
                    self._tasks.pop(request_id, None)

    def is_current(self, request_id: str) -> bool:
        """Check whether a request is still the active request."""
        with self._lock:
            return self._current_request_id == request_id

    def assert_current(self, request_id: str) -> None:
        """Raise StaleRequestError if the request is not the active request."""
        if not self.is_current(request_id):
            raise StaleRequestError(f"Request {request_id} is stale or was interrupted.")

    def current_request_id(self) -> str | None:
        """Return the active request ID, or None if nothing is active."""
        with self._lock:
            return self._current_request_id


_global_interruption_controller = InterruptionController()


def get_interruption_controller() -> InterruptionController:
    return _global_interruption_controller