import React from "react";
import { Badge } from "@/components/ui/badge";
import { Task, TaskStatus } from "@/types/api";
import { Clock, AlertTriangle, CheckCircle, Play, XCircle, RotateCcw, Skull } from "lucide-react";

interface TaskStatusBadgeProps {
  task: Partial<Task>;
  showReason?: boolean;
}

export function TaskStatusBadge({ task, showReason = true }: TaskStatusBadgeProps) {
  const status = (task.status || "PENDING") as TaskStatus;

  const getVariant = () => {
    switch (status) {
      case "SUCCEEDED":
        return "success";
      case "RUNNING":
        return "info";
      case "RETRY_WAIT":
      case "SCHEDULED":
        return "warning";
      case "FAILED":
      case "TIMED_OUT":
      case "DEAD":
        return "destructive";
      case "CANCELLED":
      case "PENDING":
      case "QUEUED":
      default:
        return "secondary";
    }
  };

  const getIcon = () => {
    switch (status) {
      case "SUCCEEDED":
        return <CheckCircle className="w-3.5 h-3.5 mr-1 text-emerald-600" />;
      case "RUNNING":
        return <Play className="w-3.5 h-3.5 mr-1 text-blue-600 animate-pulse" />;
      case "RETRY_WAIT":
        return <RotateCcw className="w-3.5 h-3.5 mr-1 text-amber-600" />;
      case "DEAD":
        return <Skull className="w-3.5 h-3.5 mr-1 text-red-600" />;
      case "FAILED":
      case "TIMED_OUT":
        return <XCircle className="w-3.5 h-3.5 mr-1 text-red-600" />;
      case "CANCELLED":
        return <AlertTriangle className="w-3.5 h-3.5 mr-1 text-slate-500" />;
      case "PENDING":
      case "QUEUED":
      case "SCHEDULED":
      default:
        return <Clock className="w-3.5 h-3.5 mr-1 text-slate-500" />;
    }
  };

  const getExplanation = (): string => {
    if (task.status_reason) {
      return task.status_reason;
    }
    switch (status) {
      case "RUNNING":
        return `Executing on ${task.worker_id || task.current_worker_id || "worker"} (Attempt ${task.attempt_count ?? 1}/${task.max_attempts ?? 3})`;
      case "SUCCEEDED":
        return task.attempt_count && task.attempt_count > 1
          ? `Completed successfully after ${task.attempt_count} attempts`
          : "Completed execution normally";
      case "RETRY_WAIT":
        return `Transient failure encountered; scheduled to retry (Attempt ${task.attempt_count}/${task.max_attempts})`;
      case "DEAD":
        return `All ${task.max_attempts} retry attempts exhausted; moved to Dead Letter Queue`;
      case "TIMED_OUT":
        return `Exceeded execution limit of ${task.timeout_seconds || 300} seconds`;
      case "CANCELLED":
        return "Execution was cancelled by operator request";
      case "SCHEDULED":
        return task.scheduled_at ? `Scheduled for future run at ${new Date(task.scheduled_at).toLocaleTimeString()}` : "Awaiting schedule trigger";
      case "QUEUED":
        return `Waiting in '${task.queue || "default"}' queue behind priority backlog`;
      case "PENDING":
        return "Received and durably committed; pending outbox dispatch";
      case "FAILED":
      default:
        return task.error || "Non-retryable execution failure";
    }
  };

  return (
    <div className="flex flex-col items-start gap-1">
      <Badge variant={getVariant()} className="font-mono text-xs flex items-center">
        {getIcon()}
        {status}
      </Badge>
      {showReason && (
        <span className="text-[11px] text-muted-foreground leading-tight line-clamp-1 max-w-xs" title={getExplanation()}>
          {getExplanation()}
        </span>
      )}
    </div>
  );
}
