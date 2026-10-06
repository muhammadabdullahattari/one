"use client";

import React, { use } from "react";
import Link from "next/link";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useTaskDetail, useCancelTask, useRetryTask } from "@/lib/api-hooks";
import { TaskStatusBadge } from "@/components/task/task-status-badge";
import {
  ArrowLeft,
  RotateCcw,
  XCircle,
  Clock,
  Layers,
  Server,
  Code,
  History,
} from "lucide-react";
import { useState } from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

export default function TaskDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const taskId = resolvedParams.id;
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const { data: task, isLoading, error } = useTaskDetail(taskId);

  const cancelTask = useCancelTask();
  const retryTask = useRetryTask();

  if (isLoading) {
    return (
      <div className="p-12 text-center text-sm text-muted-foreground">
        Loading task execution details...
      </div>
    );
  }

  if (error || !task) {
    return (
      <div className="space-y-4">
        <Link href="/tasks">
          <Button variant="ghost" size="sm" className="gap-2">
            <ArrowLeft className="w-4 h-4" /> Back to Backlog
          </Button>
        </Link>
        <Card className="p-8 text-center text-destructive">
          Task not found or failed to load.
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link href="/tasks">
            <Button variant="outline" size="sm">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-foreground font-mono">
                {task.task_type}
              </h1>
              <span className="text-xs font-mono text-muted-foreground">({task.task_id})</span>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              Tenant: {task.tenant_id} • Queue: {task.queue}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {["PENDING", "QUEUED", "RUNNING"].includes(task.status) && (
            <Button
              variant="destructive"
              size="sm"
              className="gap-2"
              onClick={() => setCancelModalOpen(true)}
              disabled={cancelTask.isPending}
            >
              <XCircle className="w-4 h-4" />
              Cancel Task
            </Button>
          )}
          {["FAILED", "DEAD"].includes(task.status) && (
            <Button
              variant="default"
              size="sm"
              className="gap-2"
              onClick={() => retryTask.mutate(task.task_id)}
              disabled={retryTask.isPending}
            >
              <RotateCcw className="w-4 h-4" />
              Retry Task
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">
            Current Status
          </p>
          <div className="mt-2">
            <TaskStatusBadge task={task} showReason={true} />
          </div>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">
            Attempt Progress
          </p>
          <div className="mt-2 text-xl font-bold font-mono">
            {task.attempt_count} / {task.max_attempts}
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">Timeout: {task.timeout_seconds}s</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">
            Assigned Worker
          </p>
          <div className="mt-2 text-sm font-semibold font-mono truncate">
            {task.worker_id || task.current_worker_id || "Unassigned"}
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">Queue: {task.queue}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">
            Submission Time
          </p>
          <div className="mt-2 text-xs font-mono font-medium">
            {new Date(task.created_at).toLocaleString()}
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">
            Priority: {task.priority}
          </p>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="py-3 border-b border-border flex flex-row items-center gap-2">
            <Code className="w-4 h-4 text-primary" />
            <CardTitle className="text-sm font-semibold">Task Payload (JSON)</CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <pre className="p-3 bg-muted/40 rounded-lg text-xs font-mono overflow-auto max-h-60">
              {JSON.stringify(task.payload || {}, null, 2)}
            </pre>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="py-3 border-b border-border flex flex-row items-center gap-2">
            <Code className="w-4 h-4 text-emerald-500" />
            <CardTitle className="text-sm font-semibold">Execution Result (JSON)</CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <pre className="p-3 bg-muted/40 rounded-lg text-xs font-mono overflow-auto max-h-60">
              {JSON.stringify(task.result || task.error || { status: "Awaiting execution" }, null, 2)}
            </pre>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="py-3 border-b border-border flex flex-row items-center gap-2">
          <History className="w-4 h-4 text-blue-500" />
          <CardTitle className="text-sm font-semibold">Attempt History</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {!task.attempts?.length ? (
            <div className="p-6 text-center text-xs text-muted-foreground">No attempts recorded yet.</div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="border-b border-border bg-muted/30 font-mono text-muted-foreground">
                <tr>
                  <th className="py-2.5 px-4">Attempt #</th>
                  <th className="py-2.5 px-4">Worker Node</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4">Started At</th>
                  <th className="py-2.5 px-4">Finished At</th>
                  <th className="py-2.5 px-4">Error Diagnostics</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {task.attempts.map((att) => (
                  <tr key={att.attempt_id} className="hover:bg-muted/20">
                    <td className="py-2.5 px-4 font-mono font-semibold">#{att.attempt_number}</td>
                    <td className="py-2.5 px-4 font-mono">{att.worker_id}</td>
                    <td className="py-2.5 px-4">
                      <Badge variant={att.status === "SUCCEEDED" ? "success" : "destructive"}>
                        {att.status}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-4 text-muted-foreground font-mono">
                      {att.started_at ? new Date(att.started_at).toLocaleTimeString() : "-"}
                    </td>
                    <td className="py-2.5 px-4 text-muted-foreground font-mono">
                      {att.finished_at ? new Date(att.finished_at).toLocaleTimeString() : "-"}
                    </td>
                    <td className="py-2.5 px-4 font-mono text-[11px] text-destructive max-w-xs truncate">
                      {att.error_class ? `${att.error_class}: ${att.error_message_redacted}` : "None"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={cancelModalOpen}
        onOpenChange={setCancelModalOpen}
        title="Cancel Task Execution"
        description={`Are you sure you want to abort task "${task.task_id}"? If currently running, the worker lease will be revoked.`}
        confirmLabel="Cancel Task"
        variant="destructive"
        loading={cancelTask.isPending}
        onConfirm={() => cancelTask.mutate(task.task_id)}
      />
    </div>
  );
}
