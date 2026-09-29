class TaskEngineError(Exception):
    pass


class TaskNotFoundError(TaskEngineError):
    pass


class InvalidStateTransitionError(TaskEngineError):
    pass


class TaskRateLimitExceededError(TaskEngineError):
    pass


class IdempotencyConflictError(TaskEngineError):
    pass


class QueueNotFoundError(TaskEngineError):
    pass


class WorkerNotFoundError(TaskEngineError):
    pass


class ScheduleNotFoundError(TaskEngineError):
    pass


class FatalTaskError(TaskEngineError):
    pass


class RetryableTaskError(TaskEngineError):
    pass
