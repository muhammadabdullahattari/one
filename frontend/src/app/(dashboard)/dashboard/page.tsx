"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  useTasks,
  useQueues,
  useWorkers,
  useDLQ,
  useAnalyticsThroughput,
  useSubmitTask,
} from "@/lib/api-hooks";
import { BaseChart } from "@/components/charts/base-chart";
import { TaskStatusBadge } from "@/components/task/task-status-badge";
import {
  Activity,
  Layers,
  Server,
  AlertOctagon,
  TrendingUp,
  PlusCircle,
  ArrowUpRight,
  RefreshCw,
} from "lucide-react";

export default function DashboardPage() {
  const { data: tasksData, isLoading: tasksLoading, refetch: refetchTasks } = useTasks({ limit: 5 });
  const { data: queuesData } = useQueues();
  const { data: workersData } = useWorkers();
  const { data: dlqData } = useDLQ();
  const { data: throughputData, isLoading: throughputLoading } = useAnalyticsThroughput(24);

  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [taskType, setTaskType] = useState("");
  const [queueSelection, setQueueSelection] = useState("default");
  const [customQueue, setCustomQueue] = useState("");
  const [priority, setPriority] = useState(5);
  const [formError, setFormError] = useState<string | null>(null);
  const submitTask = useSubmitTask();

  const availableQueues = Array.from(
    new Set(["default", ...(queuesData?.items.map((q) => q.queue_name) || [])])
  );

  const activeWorkers = workersData?.items.filter((w) => w.status === "active") || [];
  const activeWorkersCount = activeWorkers.length;
  const totalBusySlots =
    activeWorkers.reduce((acc, w) => acc + (w.active_task_count || 0), 0);
  const totalCapacitySlots =
    activeWorkers.reduce((acc, w) => acc + (w.concurrency || 0), 0);

  const totalQueues = queuesData?.items.length || 0;
  const dlqCount = dlqData?.total || 0;

  const chartOptions = useMemo(
    () => ({
      tooltip: { trigger: "axis" },
      legend: { data: ["Incoming Tasks/s", "Outgoing Tasks/s"], textStyle: { color: "#64748b" } },
      grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data:
          throughputData?.points.map((p) =>
            new Date(p.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          ) || [],
        axisLine: { lineStyle: { color: "#e2e8f0" } },
      },
      yAxis: {
        type: "value",
        axisLine: { lineStyle: { color: "#e2e8f0" } },
        splitLine: { lineStyle: { color: "#f1f5f9" } },
      },
      series: [
        {
          name: "Incoming Tasks/s",
          type: "line",
          smooth: true,
          data: throughputData?.points.map((p) => p.incoming_rate) || [],
          itemStyle: { color: "#3b82f6" },
          areaStyle: { opacity: 0.1, color: "#3b82f6" },
        },
        {
          name: "Outgoing Tasks/s",
          type: "line",
          smooth: true,
          data: throughputData?.points.map((p) => p.outgoing_rate) || [],
          itemStyle: { color: "#10b981" },
          areaStyle: { opacity: 0.1, color: "#10b981" },
        },
      ],
    }),
    [throughputData]
  );

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskType.trim()) return;
    setFormError(null);
    const targetQueue =
      queueSelection === "custom"
        ? customQueue.trim() || "default"
        : queueSelection;

    try {
      await submitTask.mutateAsync({
        task_type: taskType.trim(),
        queue: targetQueue,
        priority: Number(priority),
      });
      setTaskType("");
      setQueueSelection("default");
      setCustomQueue("");
      setPriority(5);
      setShowSubmitModal(false);
    } catch (err: any) {
      setFormError(
        err.message || "Failed to submit task. Please verify your input parameters."
      );
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Operational Overview</h1>
          <p className="text-sm text-muted-foreground">
            Real-time telemetry and state across your distributed worker cluster.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => refetchTasks()} className="gap-2">
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </Button>
          <Button size="sm" onClick={() => setShowSubmitModal(true)} className="gap-2">
            <PlusCircle className="w-4 h-4" />
            Submit Task
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Worker Fleet
            </CardTitle>
            <Server className="w-4 h-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{activeWorkersCount} Active</div>
            <p className="text-xs text-muted-foreground mt-1">
              {totalBusySlots} of {totalCapacitySlots} slots occupied
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Configured Queues
            </CardTitle>
            <Layers className="w-4 h-4 text-indigo-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalQueues} Queues</div>
            <p className="text-xs text-muted-foreground mt-1">Ready for distributed dispatch</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Current Throughput
            </CardTitle>
            <TrendingUp className="w-4 h-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {throughputData?.current_incoming_tps || 0} TPS
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Outgoing: {throughputData?.current_outgoing_tps || 0} TPS
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Dead Letter Queue
            </CardTitle>
            <AlertOctagon className="w-4 h-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{dlqCount} Tasks</div>
            <p className="text-xs text-muted-foreground mt-1">Failed attempts awaiting replay</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center justify-between">
              <span>Throughput Telemetry (Incoming vs Outgoing)</span>
              <Link href="/metrics" className="text-xs text-primary flex items-center gap-1 hover:underline">
                View detailed charts <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            </CardTitle>
            <CardDescription>24-hour rate of tasks ingested vs completed</CardDescription>
          </CardHeader>
          <CardContent>
            <BaseChart options={chartOptions} height={280} loading={throughputLoading} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center justify-between">
              <span>Live Console Shortcut</span>
              <Activity className="w-4 h-4 text-emerald-500" />
            </CardTitle>
            <CardDescription>Flower-equivalent live operational monitoring</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-muted-foreground leading-relaxed">
              Inspect active worker assignments, task lifecycle explanations, and queue backlogs in one continuous real-time monitor.
            </p>
            <div className="p-3 bg-muted/40 rounded-lg space-y-2 text-xs font-mono">
              <div className="flex justify-between">
                <span>Active Slots:</span>
                <span className="font-semibold text-foreground">{totalBusySlots}</span>
              </div>
              <div className="flex justify-between">
                <span>Total Capacity:</span>
                <span className="font-semibold text-foreground">{totalCapacitySlots}</span>
              </div>
              <div className="flex justify-between">
                <span>Utilization:</span>
                <span className="font-semibold text-emerald-600">
                  {totalCapacitySlots > 0 ? Math.round((totalBusySlots / totalCapacitySlots) * 100) : 0}%
                </span>
              </div>
            </div>
            <Link href="/live" className="w-full inline-block">
              <Button className="w-full gap-2">
                <Activity className="w-4 h-4" />
                Launch Live Console
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base font-semibold">Recent Task Executions</CardTitle>
            <CardDescription>Live backlog stream with status reasons</CardDescription>
          </div>
          <Link href="/tasks" className="text-xs text-primary flex items-center gap-1 hover:underline">
            View full backlog <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </CardHeader>
        <CardContent>
          {tasksLoading ? (
            <div className="p-8 text-center text-sm text-muted-foreground">Loading recent tasks...</div>
          ) : !tasksData?.items.length ? (
            <div className="p-8 text-center text-sm text-muted-foreground">No tasks executed yet.</div>
          ) : (
            <div className="divide-y divide-border">
              {tasksData.items.map((task) => (
                <div key={task.task_id} className="py-3 flex items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Link href={`/tasks/${task.task_id}`} className="font-medium text-sm text-foreground hover:underline">
                        {task.task_type}
                      </Link>
                      <span className="text-xs font-mono text-muted-foreground">({task.queue})</span>
                    </div>
                    <p className="text-xs font-mono text-muted-foreground">{task.task_id}</p>
                  </div>
                  <TaskStatusBadge task={task} />
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Task Submission Modal */}
      {showSubmitModal && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <Card className="w-full max-w-md shadow-2xl">
            <CardHeader>
              <CardTitle className="text-lg">Submit New Task</CardTitle>
              <CardDescription>Dispatch a task to the asynchronous worker pool</CardDescription>
            </CardHeader>
            <form onSubmit={handleCreateTask}>
              <CardContent className="space-y-4">
                {formError && (
                  <div className="p-3 text-xs rounded-md bg-destructive/10 text-destructive border border-destructive/20 font-medium">
                    {formError}
                  </div>
                )}
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-muted-foreground">Task Type *</label>
                  <Input
                    placeholder="e.g. email.send or reports.daily"
                    value={taskType}
                    onChange={(e) => setTaskType(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-muted-foreground">Queue</label>
                  <select
                    value={queueSelection}
                    onChange={(e) => {
                      setQueueSelection(e.target.value);
                      if (e.target.value !== "custom") {
                        setCustomQueue("");
                      }
                    }}
                    className="w-full text-xs h-9 rounded-md border border-input bg-background px-3 text-foreground"
                  >
                    {availableQueues.map((q) => (
                      <option key={q} value={q}>
                        {q} {q === "default" ? "(system default)" : ""}
                      </option>
                    ))}
                    <option value="custom">+ Create new queue...</option>
                  </select>
                  {queueSelection === "custom" && (
                    <Input
                      placeholder="Enter new queue name (e.g. notifications)"
                      value={customQueue}
                      onChange={(e) => setCustomQueue(e.target.value)}
                      className="mt-1.5 text-xs font-mono h-8"
                      required
                    />
                  )}
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-muted-foreground">Priority (1-10)</label>
                  <Input
                    type="number"
                    min={1}
                    max={10}
                    value={priority}
                    onChange={(e) => setPriority(Number(e.target.value))}
                  />
                </div>
              </CardContent>
              <div className="p-6 pt-0 flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setShowSubmitModal(false);
                    setFormError(null);
                  }}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={submitTask.isPending}>
                  {submitTask.isPending ? "Submitting..." : "Submit Task"}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
}
