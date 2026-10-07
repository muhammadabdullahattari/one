export class TaskEngineError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TaskEngineError";
  }
}

export class TaskNotFoundError extends TaskEngineError {
  public readonly taskId: string;

  constructor(taskId: string) {
    super(`Task not found: ${taskId}`);
    this.name = "TaskNotFoundError";
    this.taskId = taskId;
  }
}

export class TaskExecutionError extends TaskEngineError {
  public readonly taskId?: string | undefined;
  public readonly errorClass?: string | undefined;

  constructor(
    message: string,
    taskId?: string | undefined,
    errorClass?: string | undefined
  ) {
    super(message);
    this.name = "TaskExecutionError";
    this.taskId = taskId;
    this.errorClass = errorClass;
  }
}

export class TaskTimeoutError extends TaskEngineError {
  public readonly taskId: string;
  public readonly timeoutMs: number;

  constructor(taskId: string, timeoutMs: number) {
    super(`Task '${taskId}' timed out after ${timeoutMs}ms`);
    this.name = "TaskTimeoutError";
    this.taskId = taskId;
    this.timeoutMs = timeoutMs;
  }
}

export class TaskCancelledError extends TaskEngineError {
  public readonly taskId: string;

  constructor(taskId: string) {
    super(`Task '${taskId}' was cancelled`);
    this.name = "TaskCancelledError";
    this.taskId = taskId;
  }
}

export class AuthenticationError extends TaskEngineError {
  constructor(message: string = "Authentication failed") {
    super(message);
    this.name = "AuthenticationError";
  }
}

export class ConnectionError extends TaskEngineError {
  constructor(message: string) {
    super(message);
    this.name = "ConnectionError";
  }
}
