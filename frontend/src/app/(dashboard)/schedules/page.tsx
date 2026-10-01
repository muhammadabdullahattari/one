"use client";

import { useState } from "react";
import {
  Calendar,
  Clock,
  Play,
  Plus,
  RefreshCw,
  Trash2,
  Power,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  X,
} from "lucide-react";
import {
  useSchedules,
  useCreateSchedule,
  useUpdateSchedule,
  useDeleteSchedule,
  useTriggerSchedule,
  useQueues,
} from "@/lib/api-hooks";
import { ScheduleItem } from "@/types/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function SchedulesPage() {
  const [enabledOnly, setEnabledOnly] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedSchedule, setSelectedSchedule] = useState<ScheduleItem | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(
    null
  );

  const { data: schedulesData, isLoading, refetch, isRefetching } = useSchedules(enabledOnly);
  const { data: queuesData } = useQueues();
  const createSchedule = useCreateSchedule();
  const updateSchedule = useUpdateSchedule();
  const deleteSchedule = useDeleteSchedule();
  const triggerSchedule = useTriggerSchedule();

  // Create Form State
  const [formTaskType, setFormTaskType] = useState("");
  const [formQueue, setFormQueue] = useState("default");
  const [recurrenceType, setRecurrenceType] = useState<"cron" | "interval">("cron");
  const [formCron, setFormCron] = useState("0 * * * *");
  const [formInterval, setFormInterval] = useState("300");
  const [formTimezone, setFormTimezone] = useState("UTC");
  const [formMisfire, setFormMisfire] = useState("coalescing");
  const [formPayload, setFormPayload] = useState("{}");
  const [formEnabled, setFormEnabled] = useState(true);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setFeedback(null);
    let parsedPayload = {};
    if (formPayload.trim()) {
      try {
        parsedPayload = JSON.parse(formPayload);
      } catch {
        setFeedback({ type: "error", message: "Payload must be valid JSON." });
        return;
      }
    }

    try {
      await createSchedule.mutateAsync({
        task_type: formTaskType.trim(),
        queue: formQueue.trim() || "default",
        cron: recurrenceType === "cron" ? formCron.trim() : undefined,
        interval_seconds:
          recurrenceType === "interval" ? parseInt(formInterval, 10) : undefined,
        timezone: formTimezone.trim() || "UTC",
        misfire_policy: formMisfire,
        enabled: formEnabled,
        payload: parsedPayload,
      });
      setShowCreateModal(false);
      setFormTaskType("");
      setFormPayload("{}");
      setFeedback({ type: "success", message: "Recurring schedule created successfully." });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create schedule";
      setFeedback({ type: "error", message: msg });
    }
  };

  const handleToggle = async (schedule: ScheduleItem) => {
    setFeedback(null);
    try {
      await updateSchedule.mutateAsync({
        scheduleId: schedule.schedule_id,
        body: { enabled: !schedule.enabled },
      });
      setFeedback({
        type: "success",
        message: `Schedule ${schedule.enabled ? "paused" : "activated"} successfully.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to toggle schedule";
      setFeedback({ type: "error", message: msg });
    }
  };

  const handleTrigger = async (schedule: ScheduleItem) => {
    setFeedback(null);
    try {
      const res = await triggerSchedule.mutateAsync(schedule.schedule_id);
      setFeedback({
        type: "success",
        message: `Triggered execution for '${schedule.task_type}'. Spawned Task ID: ${res.task_id}`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to trigger schedule";
      setFeedback({ type: "error", message: msg });
    }
  };

  const handleDelete = async (schedule: ScheduleItem) => {
    if (!confirm(`Are you sure you want to permanently delete schedule for '${schedule.task_type}'?`)) {
      return;
    }
    setFeedback(null);
    try {
      await deleteSchedule.mutateAsync(schedule.schedule_id);
      setFeedback({ type: "success", message: "Schedule deleted successfully." });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete schedule";
      setFeedback({ type: "error", message: msg });
    }
  };

  const formatCountdown = (nextRunStr: string | null) => {
    if (!nextRunStr) return "N/A";
    const diff = new Date(nextRunStr).getTime() - Date.now();
    if (diff <= 0) return "Due now";
    const totalSecs = Math.floor(diff / 1000);
    const hours = Math.floor(totalSecs / 3600);
    const mins = Math.floor((totalSecs % 3600) / 60);
    const secs = totalSecs % 60;
    if (hours > 0) return `in ${hours}h ${mins}m`;
    if (mins > 0) return `in ${mins}m ${secs}s`;
    return `in ${secs}s`;
  };

  const schedules = schedulesData?.items || [];
  const queues = queuesData?.items || [];

  return (
    <div className="space-y-6">
      {/* Top Banner / Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Calendar className="h-6 w-6 text-primary" />
            Recurring Schedules
          </h1>
          <p className="text-sm text-muted-foreground">
            Cron expressions and fixed intervals for automated background workflows.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isRefetching}
            className="gap-1.5"
          >
            <RefreshCw className={`h-4 w-4 ${isRefetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          <Button
            size="sm"
            onClick={() => setShowCreateModal(true)}
            className="gap-1.5"
          >
            <Plus className="h-4 w-4" />
            New Schedule
          </Button>
        </div>
      </div>

      {/* Global Feedback Banner */}
      {feedback && (
        <div
          className={`flex items-center justify-between p-3.5 rounded-lg border text-sm ${
            feedback.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
              : "bg-destructive/10 border-destructive/30 text-destructive"
          }`}
        >
          <div className="flex items-center gap-2">
            {feedback.type === "success" ? (
              <CheckCircle2 className="h-4 w-4 shrink-0" />
            ) : (
              <AlertTriangle className="h-4 w-4 shrink-0" />
            )}
            <span>{feedback.message}</span>
          </div>
          <button
            onClick={() => setFeedback(null)}
            className="text-muted-foreground hover:text-foreground p-1"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Filters bar */}
      <div className="flex items-center justify-between bg-card p-3 rounded-lg border border-border">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Filter:
          </span>
          <button
            onClick={() => setEnabledOnly(false)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              !enabledOnly
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            All Schedules ({schedulesData?.total ?? 0})
          </button>
          <button
            onClick={() => setEnabledOnly(true)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              enabledOnly
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            Active Only
          </button>
        </div>
      </div>

      {/* Schedules Cards / Table */}
      {isLoading ? (
        <div className="p-12 text-center text-sm text-muted-foreground animate-pulse">
          Loading scheduled jobs...
        </div>
      ) : schedules.length === 0 ? (
        <Card className="text-center py-12">
          <CardContent className="space-y-3">
            <Clock className="h-10 w-10 text-muted-foreground mx-auto" />
            <div className="text-base font-semibold">No schedules defined yet</div>
            <p className="text-sm text-muted-foreground max-w-sm mx-auto">
              Create a recurring schedule with standard Cron syntax or fixed intervals to automate tasks.
            </p>
            <Button
              size="sm"
              onClick={() => setShowCreateModal(true)}
              className="gap-1.5 mt-2"
            >
              <Plus className="h-4 w-4" />
              Create First Schedule
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {schedules.map((schedule) => (
            <Card
              key={schedule.schedule_id}
              className={`transition-all border ${
                schedule.enabled
                  ? "border-border hover:border-primary/40"
                  : "border-border/50 bg-card/60 opacity-80"
              }`}
            >
              <div className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="space-y-1.5 min-w-0">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <span className="font-semibold text-base text-foreground font-mono">
                      {schedule.task_type}
                    </span>
                    <Badge variant={schedule.enabled ? "default" : "secondary"}>
                      {schedule.enabled ? "ENABLED" : "PAUSED"}
                    </Badge>
                    <Badge variant="outline" className="font-mono text-xs">
                      queue: {schedule.queue}
                    </Badge>
                    <Badge variant="outline" className="text-xs">
                      misfire: {schedule.misfire_policy}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap pt-1">
                    <div className="flex items-center gap-1.5">
                      <Clock className="h-3.5 w-3.5 text-primary" />
                      <span className="font-mono font-medium text-foreground">
                        {schedule.cron ? `cron("${schedule.cron}")` : `every ${schedule.interval_seconds}s`}
                      </span>
                      <span>({schedule.timezone})</span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <span className="text-muted-foreground">Next run:</span>
                      <span
                        className={`font-semibold ${
                          schedule.enabled ? "text-emerald-400 font-mono" : "text-muted-foreground"
                        }`}
                      >
                        {schedule.enabled
                          ? `${new Date(schedule.next_run_at || "").toLocaleTimeString()} (${formatCountdown(
                              schedule.next_run_at
                            )})`
                          : "Paused"}
                      </span>
                    </div>

                    {schedule.last_run_at && (
                      <div className="flex items-center gap-1.5">
                        <span className="text-muted-foreground">Last ran:</span>
                        <span>{new Date(schedule.last_run_at).toLocaleString()}</span>
                      </div>
                    )}

                    <div className="flex items-center gap-1.5">
                      <span className="text-muted-foreground">Total runs:</span>
                      <span className="font-mono">{schedule.total_run_count}</span>
                    </div>
                  </div>
                </div>

                {/* Actions Button Group */}
                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleTrigger(schedule)}
                    disabled={triggerSchedule.isPending}
                    title="Execute immediately without waiting for cron window"
                    className="gap-1.5 text-xs text-primary border-primary/30 hover:bg-primary/10"
                  >
                    <Play className="h-3.5 w-3.5 fill-primary" />
                    Trigger Now
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleToggle(schedule)}
                    disabled={updateSchedule.isPending}
                    title={schedule.enabled ? "Pause recurrence" : "Enable recurrence"}
                    className="gap-1 text-xs"
                  >
                    <Power className={`h-3.5 w-3.5 ${schedule.enabled ? "text-amber-400" : "text-emerald-400"}`} />
                    {schedule.enabled ? "Pause" : "Enable"}
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSelectedSchedule(schedule)}
                    title="View payload & details"
                    className="gap-1 text-xs"
                  >
                    <Sliders className="h-3.5 w-3.5" />
                    Details
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDelete(schedule)}
                    disabled={deleteSchedule.isPending}
                    title="Delete schedule definition"
                    className="text-destructive hover:bg-destructive/10 border-destructive/30"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Schedule Detail Modal */}
      {selectedSchedule && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
          <Card className="w-full max-w-xl max-h-[85vh] overflow-y-auto border-border shadow-2xl">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-lg font-bold flex items-center gap-2">
                <Sliders className="h-5 w-5 text-primary" />
                Schedule: {selectedSchedule.task_type}
              </CardTitle>
              <button
                onClick={() => setSelectedSchedule(null)}
                className="text-muted-foreground hover:text-foreground p-1"
              >
                <X className="h-5 w-5" />
              </button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-2.5 rounded bg-muted/50 border border-border">
                  <span className="text-muted-foreground block mb-1">Schedule UUID</span>
                  <span className="font-mono text-foreground select-all break-all">
                    {selectedSchedule.schedule_id}
                  </span>
                </div>
                <div className="p-2.5 rounded bg-muted/50 border border-border">
                  <span className="text-muted-foreground block mb-1">Target Queue</span>
                  <span className="font-mono text-foreground font-semibold">
                    {selectedSchedule.queue}
                  </span>
                </div>
                <div className="p-2.5 rounded bg-muted/50 border border-border">
                  <span className="text-muted-foreground block mb-1">Misfire Policy</span>
                  <span className="text-foreground capitalize">
                    {selectedSchedule.misfire_policy}
                  </span>
                </div>
                <div className="p-2.5 rounded bg-muted/50 border border-border">
                  <span className="text-muted-foreground block mb-1">Timezone</span>
                  <span className="text-foreground font-mono">
                    {selectedSchedule.timezone}
                  </span>
                </div>
              </div>

              <div>
                <span className="text-xs font-medium text-muted-foreground block mb-1.5">
                  Static Task Payload (JSON passed to each trigger)
                </span>
                <pre className="p-3 bg-muted/70 rounded-md border border-border text-xs font-mono overflow-x-auto text-foreground">
                  {JSON.stringify(selectedSchedule.payload, null, 2)}
                </pre>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedSchedule(null)}
                >
                  Close
                </Button>
                <Button
                  size="sm"
                  onClick={() => {
                    handleTrigger(selectedSchedule);
                    setSelectedSchedule(null);
                  }}
                  className="gap-1.5"
                >
                  <Play className="h-4 w-4" />
                  Trigger Now
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Create Schedule Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
          <Card className="w-full max-w-lg border-border shadow-2xl">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-lg font-bold flex items-center gap-2">
                <Plus className="h-5 w-5 text-primary" />
                Create Recurring Schedule
              </CardTitle>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-muted-foreground hover:text-foreground p-1"
              >
                <X className="h-5 w-5" />
              </button>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreate} className="space-y-4">
                <div>
                  <label className="text-xs font-medium text-muted-foreground block mb-1">
                    Task Type *
                  </label>
                  <Input
                    placeholder="e.g. email.daily_digest or reports.generate"
                    value={formTaskType}
                    onChange={(e) => setFormTaskType(e.target.value)}
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground block mb-1">
                      Queue
                    </label>
                    <select
                      className="w-full h-9 rounded-md border border-input bg-background px-3 text-xs"
                      value={formQueue}
                      onChange={(e) => setFormQueue(e.target.value)}
                    >
                      <option value="default">default</option>
                      {queues.map((q) => (
                        <option key={q.queue_name} value={q.queue_name}>
                          {q.queue_name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-muted-foreground block mb-1">
                      Timezone
                    </label>
                    <Input
                      value={formTimezone}
                      onChange={(e) => setFormTimezone(e.target.value)}
                      placeholder="UTC"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-medium text-muted-foreground block mb-1.5">
                    Recurrence Type
                  </label>
                  <div className="flex gap-4 mb-2">
                    <label className="flex items-center gap-1.5 text-xs text-foreground cursor-pointer">
                      <input
                        type="radio"
                        name="recurrence"
                        checked={recurrenceType === "cron"}
                        onChange={() => setRecurrenceType("cron")}
                      />
                      Cron Expression
                    </label>
                    <label className="flex items-center gap-1.5 text-xs text-foreground cursor-pointer">
                      <input
                        type="radio"
                        name="recurrence"
                        checked={recurrenceType === "interval"}
                        onChange={() => setRecurrenceType("interval")}
                      />
                      Fixed Interval (seconds)
                    </label>
                  </div>

                  {recurrenceType === "cron" ? (
                    <div>
                      <Input
                        value={formCron}
                        onChange={(e) => setFormCron(e.target.value)}
                        placeholder="0 * * * * (e.g. hourly)"
                        className="font-mono text-xs"
                        required
                      />
                      <span className="text-[11px] text-muted-foreground block mt-1">
                        Format: min hour dom mon dow (e.g. &apos;*/15 * * * *&apos; or &apos;0 0 * * *&apos;)
                      </span>
                    </div>
                  ) : (
                    <div>
                      <Input
                        type="number"
                        min="1"
                        max="2592000"
                        value={formInterval}
                        onChange={(e) => setFormInterval(e.target.value)}
                        placeholder="300"
                        className="font-mono text-xs"
                        required
                      />
                      <span className="text-[11px] text-muted-foreground block mt-1">
                        Interval in seconds (e.g. 60 = every minute, 3600 = every hour)
                      </span>
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground block mb-1">
                      Misfire Policy
                    </label>
                    <select
                      className="w-full h-9 rounded-md border border-input bg-background px-3 text-xs"
                      value={formMisfire}
                      onChange={(e) => setFormMisfire(e.target.value)}
                    >
                      <option value="coalescing">Coalescing (merge missed)</option>
                      <option value="skip">Skip (ignore missed)</option>
                      <option value="catch_up">Catch Up (run each missed)</option>
                    </select>
                  </div>
                  <div className="flex items-center pt-5">
                    <label className="flex items-center gap-2 text-xs cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={formEnabled}
                        onChange={(e) => setFormEnabled(e.target.checked)}
                        className="rounded"
                      />
                      <span className="font-medium text-foreground">Enable immediately</span>
                    </label>
                  </div>
                </div>

                <div>
                  <label className="text-xs font-medium text-muted-foreground block mb-1">
                    Task Payload (JSON)
                  </label>
                  <textarea
                    rows={3}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-xs font-mono text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    value={formPayload}
                    onChange={(e) => setFormPayload(e.target.value)}
                  />
                </div>

                <div className="flex justify-end gap-2 pt-3 border-t border-border">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setShowCreateModal(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={createSchedule.isPending}
                    className="gap-1.5"
                  >
                    {createSchedule.isPending ? "Creating..." : "Save Schedule"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
