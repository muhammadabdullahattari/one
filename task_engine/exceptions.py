class TaskEngineError(Exception):
    pass


class TaskNotFoundError(TaskEngineError):
    def __init__(self, task_id: str) -> None:
        super().__init__(f"Task not found: {task_id}")
        self.task_id = task_id


class TaskExecutionError(TaskEngineError):
    def __init__(
        self, message: str, task_id: str | None = None, error_class: str | None = None
    ) -> None:
        super().__init__(message)
        self.task_id = task_id
        self.error_class = error_class


class TaskTimeoutError(TaskEngineError):
    def __init__(self, task_id: str, timeout_seconds: float) -> None:
        super().__init__(f"Task '{task_id}' timed out after {timeout_seconds}s")
        self.task_id = task_id
        self.timeout_seconds = timeout_seconds


class TaskCancelledError(TaskEngineError):
    def __init__(self, task_id: str) -> None:
        super().__init__(f"Task '{task_id}' was cancelled")
        self.task_id = task_id


class ConnectionError(TaskEngineError):
    pass


class AuthenticationError(TaskEngineError):
    pass


class ConfigurationError(TaskEngineError):
    pass
