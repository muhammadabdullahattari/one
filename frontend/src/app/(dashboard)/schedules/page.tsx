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
  Sparkles,
  Info,
  ChevronDown,
} from "lucide-react";
import {
  useSchedules,
  useCreateSchedule,
  useUpdateSchedule,
  useDeleteSchedule,
  useTriggerSchedule,
  useQueues,
  queryKeys,
} from "@/lib/api-hooks";
import { useQueryClient } from "@tanstack/react-query";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { ScheduleItem } from "@/types/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const COMMON_TIMEZONES = [
  { value: "UTC", label: "UTC (Coordinated Universal Time)" },
  { value: "America/New_York", label: "America/New_York (US Eastern, EDT/EST)" },
  { value: "America/Chicago", label: "America/Chicago (US Central, CDT/CST)" },
  { value: "America/Denver", label: "America/Denver (US Mountain, MDT/MST)" },
  { value: "America/Los_Angeles", label: "America/Los_Angeles (US Pacific, PDT/PST)" },
  { value: "Europe/London", label: "Europe/London (GMT / British Summer Time)" },
  { value: "Europe/Paris", label: "Europe/Paris (Central European Time, CET)" },
  { value: "Europe/Berlin", label: "Europe/Berlin (Central European Time, CET)" },
  { value: "Asia/Dubai", label: "Asia/Dubai (Gulf Standard Time, GST +4)" },
  { value: "Asia/Karachi", label: "Asia/Karachi (Pakistan Standard Time, PKT +5)" },
  { value: "Asia/Kolkata", label: "Asia/Kolkata (India Standard Time, IST +5:30)" },
  { value: "Asia/Dhaka", label: "Asia/Dhaka (Bangladesh Standard Time, BST +6)" },
  { value: "Asia/Bangkok", label: "Asia/Bangkok (Indochina Time, ICT +7)" },
  { value: "Asia/Singapore", label: "Asia/Singapore (Singapore Standard Time, SGT +8)" },
  { value: "Asia/Tokyo", label: "Asia/Tokyo (Japan Standard Time, JST +9)" },
  { value: "Australia/Sydney", label: "Australia/Sydney (Australian Eastern Time, AEST +10)" },
  { value: "Pacific/Auckland", label: "Pacific/Auckland (New Zealand Time, NZST +12)" },
  { value: "custom", label: "Other / Custom Timezone..." },
];

const PAYLOAD_TEMPLATES = {
  email: JSON.stringify(
    {
      recipient: "ops-team@company.com",
      subject: "Scheduled System Digest",
      template: "daily_summary",
    },
    null,
    2
  ),
  report: JSON.stringify(
    {
      report_type: "daily_summary",
      format: "pdf",
      include_charts: true,
    },
    null,
    2
  ),
  cleanup: JSON.stringify(
    {
      retention_days: 30,
      dry_run: false,
    },
    null,
    2
  ),
  empty: "{}",
};

const DAYS_OF_WEEK = [
  { id: "1", label: "Mon" },
  { id: "2", label: "Tue" },
  { id: "3", label: "Wed" },
  { id: "4", label: "Thu" },
  { id: "5", label: "Fri" },
  { id: "6", label: "Sat" },
  { id: "0", label: "Sun" },
];

function getHumanReadableCron(cron: string, tz: string): string {
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return `Custom cron schedule: "${cron}"`;

  const [min, hour, dom, mon, dow] = parts;
  const dayNames: Record<string, string> = {
    "1": "Monday",
    "2": "Tuesday",
    "3": "Wednesday",
    "4": "Thursday",
    "5": "Friday",
    "6": "Saturday",
    "0": "Sunday",
    "7": "Sunday",
  };

  if (cron === "* * * * *") return "Runs every minute";
  if (min.startsWith("*/") && hour === "*" && dom === "*" && mon === "*" && dow === "*") {
    return `Runs every ${min.replace("*/", "")} minutes`;
  }
  if (min === "0" && hour === "*" && dom === "*" && mon === "*" && dow === "*") {
    return "Runs hourly at the top of the hour (:00)";
  }
  if (!isNaN(Number(min)) && hour === "*" && dom === "*" && mon === "*" && dow === "*") {
    return `Runs hourly at minute :${min.padStart(2, "0")}`;
  }
  if (dom === "*" && mon === "*" && dow === "*" && !isNaN(Number(min)) && !isNaN(Number(hour))) {
    const formatted = `${hour.padStart(2, "0")}:${min.padStart(2, "0")}`;
    return `Runs every day at ${formatted} (${tz})`;
  }
  if (dom === "*" && mon === "*" && dow in dayNames && !isNaN(Number(min)) && !isNaN(Number(hour))) {
    const formatted = `${hour.padStart(2, "0")}:${min.padStart(2, "0")}`;
    return `Runs weekly on ${dayNames[dow]} at ${formatted} (${tz})`;
  }
  if (!isNaN(Number(dom)) && mon === "*" && dow === "*" && !isNaN(Number(min)) && !isNaN(Number(hour))) {
    const formatted = `${hour.padStart(2, "0")}:${min.padStart(2, "0")}`;
    return `Runs monthly on day ${dom} at ${formatted} (${tz})`;
  }
  return `Runs on schedule: ${cron} (${tz})`;
}

export default function SchedulesPage() {
  const queryClient = useQueryClient();
  const [enabledOnly, setEnabledOnly] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedSchedule, setSelectedSchedule] = useState<ScheduleItem | null>(null);
  const [scheduleToDelete, setScheduleToDelete] = useState<ScheduleItem | null>(null);
  const [deletingSchedule, setDeletingSchedule] = useState(false);
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
  const [formCron, setFormCron] = useState("0 9 * * *");
  const [cronFrequency, setCronFrequency] = useState<
    "every_5m" | "every_15m" | "hourly" | "daily" | "weekly" | "monthly" | "custom"
  >("daily");
  const [cronHour, setCronHour] = useState("09");
  const [cronMinute, setCronMinute] = useState("00");
  const [cronDayOfWeek, setCronDayOfWeek] = useState("1"); // Mon
  const [cronDayOfMonth, setCronDayOfMonth] = useState("1");
  const [showAdvancedCron, setShowAdvancedCron] = useState(false);

  const [formInterval, setFormInterval] = useState("300");
  const [formTimezone, setFormTimezone] = useState("UTC");
  const [customTimezone, setCustomTimezone] = useState("");
  const [formMisfire, setFormMisfire] = useState("coalescing");
  const [formPayload, setFormPayload] = useState("{}");
  const [formEnabled, setFormEnabled] = useState(true);

  const effectiveTimezone =
    formTimezone === "custom" ? customTimezone.trim() || "UTC" : formTimezone;

  const isPayloadValid = (() => {
    if (!formPayload.trim()) return true;
    try {
      JSON.parse(formPayload);
      return true;
    } catch {
      return false;
    }
  })();

  const updateCronFromVisual = (
    freq: string,
    hour: string,
    minute: string,
    dow: string,
    dom: string
  ) => {
    let expr = "0 * * * *";
    if (freq === "every_5m") expr = "*/5 * * * *";
    else if (freq === "every_15m") expr = "*/15 * * * *";
    else if (freq === "hourly") expr = `${minute} * * * *`;
    else if (freq === "daily") expr = `${minute} ${hour} * * *`;
    else if (freq === "weekly") expr = `${minute} ${hour} * * ${dow}`;
    else if (freq === "monthly") expr = `${minute} ${hour} ${dom} * *`;
    else return;
    setFormCron(expr);
  };

  const handleFrequencyChange = (freq: any) => {
    setCronFrequency(freq);
    updateCronFromVisual(freq, cronHour, cronMinute, cronDayOfWeek, cronDayOfMonth);
  };

  const handleHourChange = (newHour: string) => {
    setCronHour(newHour);
    updateCronFromVisual(cronFrequency, newHour, cronMinute, cronDayOfWeek, cronDayOfMonth);
  };

  const handleMinuteChange = (newMin: string) => {
    setCronMinute(newMin);
    updateCronFromVisual(cronFrequency, cronHour, newMin, cronDayOfWeek, cronDayOfMonth);
  };

  const handleDowChange = (newDow: string) => {
    setCronDayOfWeek(newDow);
    updateCronFromVisual(cronFrequency, cronHour, cronMinute, newDow, cronDayOfMonth);
  };

  const handleDomChange = (newDom: string) => {
    setCronDayOfMonth(newDom);
    updateCronFromVisual(cronFrequency, cronHour, cronMinute, cronDayOfWeek, newDom);
  };

  const handleFormatPayload = () => {
    try {
      const parsed = JSON.parse(formPayload || "{}");
      setFormPayload(JSON.stringify(parsed, null, 2));
    } catch {
      // noop
    }
  };

  const insertPayloadTemplate = (type: "email" | "report" | "cleanup" | "empty") => {
    setFormPayload(PAYLOAD_TEMPLATES[type]);
  };

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
        timezone: effectiveTimezone,
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

  const confirmDeleteSchedule = async () => {
    if (!scheduleToDelete) return;
    const schedule = scheduleToDelete;
    setDeletingSchedule(true);
    setFeedback(null);
    try {
      queryClient.setQueryData([...queryKeys.schedules(), enabledOnly], (old: any) => {
        if (!old?.items) return old;
        return {
          ...old,
          items: old.items.filter((s: ScheduleItem) => s.schedule_id !== schedule.schedule_id),
          total: Math.max(0, (old.total ?? old.items.length) - 1),
        };
      });
      await deleteSchedule.mutateAsync(schedule.schedule_id);
      setFeedback({
        type: "success",
        message: `Schedule for '${schedule.task_type}' deleted successfully.`,
      });
    } catch (err: unknown) {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
      const msg = err instanceof Error ? err.message : "Failed to delete schedule";
      setFeedback({ type: "error", message: msg });
    } finally {
      setDeletingSchedule(false);
      setScheduleToDelete(null);
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
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Filter:
          </span>
          <button
            onClick={() => setEnabledOnly(false)}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer ${
              !enabledOnly
                ? "border-2 border-foreground bg-foreground text-background shadow-sm ring-2 ring-foreground/20"
                : "border border-border bg-card text-muted-foreground hover:bg-muted/50 hover:text-foreground"
            }`}
          >
            All Schedules ({schedulesData?.total ?? 0})
          </button>
          <button
            onClick={() => setEnabledOnly(true)}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer ${
              enabledOnly
                ? "border-2 border-foreground bg-foreground text-background shadow-sm ring-2 ring-foreground/20"
                : "border border-border bg-card text-muted-foreground hover:bg-muted/50 hover:text-foreground"
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
                    onClick={() => setScheduleToDelete(schedule)}
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
                type="button"
                onClick={() => setSelectedSchedule(null)}
                className="text-muted-foreground hover:text-foreground hover:bg-muted p-1.5 rounded-md transition-colors cursor-pointer"
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
          <Card className="w-full max-w-xl max-h-[90vh] overflow-y-auto border-border shadow-2xl">
            <CardHeader className="flex flex-row items-center justify-between pb-3 border-b border-border sticky top-0 bg-card z-10">
              <CardTitle className="text-lg font-bold flex items-center gap-2">
                <Plus className="h-5 w-5 text-primary" />
                Create Recurring Schedule
              </CardTitle>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="text-muted-foreground hover:text-foreground hover:bg-muted p-1.5 rounded-md transition-colors cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </CardHeader>
            <CardContent className="pt-4">
              <form onSubmit={handleCreate} className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-muted-foreground block mb-1">
                    Task Type *
                  </label>
                  <Input
                    placeholder="e.g. email.daily_digest or reports.generate"
                    value={formTaskType}
                    onChange={(e) => setFormTaskType(e.target.value)}
                    required
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-muted-foreground block mb-1">
                      Queue
                    </label>
                    <select
                      className="w-full h-9 rounded-md border border-input bg-background px-3 text-xs text-foreground cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      value={formQueue}
                      onChange={(e) => setFormQueue(e.target.value)}
                    >
                      <option value="default">default (system default)</option>
                      {queues
                        .filter((q) => q.queue_name !== "default")
                        .map((q) => (
                          <option key={q.queue_name} value={q.queue_name}>
                            {q.queue_name}
                          </option>
                        ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-muted-foreground block mb-1">
                      Timezone
                    </label>
                    <select
                      className="w-full h-9 rounded-md border border-input bg-background px-3 text-xs text-foreground cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      value={formTimezone}
                      onChange={(e) => setFormTimezone(e.target.value)}
                    >
                      {COMMON_TIMEZONES.map((tz) => (
                        <option key={tz.value} value={tz.value}>
                          {tz.label}
                        </option>
                      ))}
                    </select>
                    {formTimezone === "custom" && (
                      <Input
                        placeholder="e.g. Europe/Rome"
                        value={customTimezone}
                        onChange={(e) => setCustomTimezone(e.target.value)}
                        className="mt-1.5 text-xs font-mono"
                        required
                      />
                    )}
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold text-muted-foreground block mb-1.5">
                    Recurrence Type
                  </label>
                  <div className="flex gap-4 mb-2.5">
                    <label className="flex items-center gap-1.5 text-xs text-foreground cursor-pointer font-medium">
                      <input
                        type="radio"
                        name="recurrence"
                        checked={recurrenceType === "cron"}
                        onChange={() => setRecurrenceType("cron")}
                        className="cursor-pointer"
                      />
                      Cron Schedule (Calendar & Clock)
                    </label>
                    <label className="flex items-center gap-1.5 text-xs text-foreground cursor-pointer font-medium">
                      <input
                        type="radio"
                        name="recurrence"
                        checked={recurrenceType === "interval"}
                        onChange={() => setRecurrenceType("interval")}
                        className="cursor-pointer"
                      />
                      Fixed Interval (Seconds)
                    </label>
                  </div>

                  {recurrenceType === "cron" ? (
                    <div className="space-y-3 p-3.5 bg-muted/40 rounded-lg border border-border">
                      <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-muted-foreground block">
                          Schedule Frequency
                        </label>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                          {[
                            { id: "every_5m", label: "Every 5 Min" },
                            { id: "every_15m", label: "Every 15 Min" },
                            { id: "hourly", label: "Hourly" },
                            { id: "daily", label: "Daily" },
                            { id: "weekly", label: "Weekly" },
                            { id: "monthly", label: "Monthly" },
                            { id: "custom", label: "Custom Cron" },
                          ].map((preset) => (
                            <button
                              key={preset.id}
                              type="button"
                              onClick={() => handleFrequencyChange(preset.id)}
                              className={cn(
                                "px-2.5 py-1.5 rounded-md text-xs font-medium border text-center transition-all cursor-pointer",
                                cronFrequency === preset.id
                                  ? "bg-primary text-primary-foreground border-primary shadow-sm"
                                  : "bg-background text-foreground border-input hover:bg-accent hover:border-primary/40"
                              )}
                            >
                              {preset.label}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Visual Clock / Calendar Controls */}
                      {(cronFrequency === "daily" ||
                        cronFrequency === "weekly" ||
                        cronFrequency === "monthly") && (
                        <div className="p-3 bg-background rounded-md border border-border space-y-3">
                          {/* Weekly Calendar Day-of-Week Picker */}
                          {cronFrequency === "weekly" && (
                            <div className="space-y-1.5">
                              <label className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                                <Calendar className="w-3.5 h-3.5 text-primary" />
                                Day of Week
                              </label>
                              <div className="flex gap-1.5 flex-wrap">
                                {DAYS_OF_WEEK.map((d) => (
                                  <button
                                    key={d.id}
                                    type="button"
                                    onClick={() => handleDowChange(d.id)}
                                    className={cn(
                                      "px-3 py-1.5 rounded-md text-xs font-semibold transition-all border cursor-pointer",
                                      cronDayOfWeek === d.id
                                        ? "bg-primary text-primary-foreground border-primary shadow-sm"
                                        : "bg-muted/50 text-muted-foreground border-border hover:bg-accent hover:text-foreground"
                                    )}
                                  >
                                    {d.label}
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Monthly Day-of-Month Picker */}
                          {cronFrequency === "monthly" && (
                            <div className="space-y-1.5">
                              <label className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                                <Calendar className="w-3.5 h-3.5 text-primary" />
                                Day of Month (1 - 31)
                              </label>
                              <div className="flex items-center gap-2">
                                <span className="text-xs text-muted-foreground">Run on day</span>
                                <select
                                  className="h-8 rounded-md border border-input bg-background px-2 text-xs font-mono cursor-pointer"
                                  value={cronDayOfMonth}
                                  onChange={(e) => handleDomChange(e.target.value)}
                                >
                                  {Array.from({ length: 31 }, (_, i) => String(i + 1)).map(
                                    (d) => (
                                      <option key={d} value={d}>
                                        {d}
                                      </option>
                                    )
                                  )}
                                </select>
                                <span className="text-xs text-muted-foreground">of every month</span>
                              </div>
                            </div>
                          )}

                          {/* Clock Picker: Hour & Minute */}
                          <div className="space-y-1.5">
                            <label className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                              <Clock className="w-3.5 h-3.5 text-primary" />
                              Execution Time ({effectiveTimezone})
                            </label>
                            <div className="flex items-center gap-2 flex-wrap">
                              <div className="flex items-center gap-1.5 bg-muted/40 p-1.5 rounded-md border border-border">
                                <select
                                  className="h-8 rounded-md border border-input bg-background px-2 text-xs font-mono font-semibold cursor-pointer"
                                  value={cronHour}
                                  onChange={(e) => handleHourChange(e.target.value)}
                                >
                                  {Array.from({ length: 24 }, (_, i) =>
                                    String(i).padStart(2, "0")
                                  ).map((h) => (
                                    <option key={h} value={h}>
                                      {h}:00 ({Number(h) % 12 || 12}{" "}
                                      {Number(h) >= 12 ? "PM" : "AM"})
                                    </option>
                                  ))}
                                </select>
                                <span className="text-xs font-bold text-muted-foreground">:</span>
                                <select
                                  className="h-8 rounded-md border border-input bg-background px-2 text-xs font-mono font-semibold cursor-pointer"
                                  value={cronMinute}
                                  onChange={(e) => handleMinuteChange(e.target.value)}
                                >
                                  {[
                                    "00",
                                    "05",
                                    "10",
                                    "15",
                                    "20",
                                    "25",
                                    "30",
                                    "35",
                                    "40",
                                    "45",
                                    "50",
                                    "55",
                                  ].map((m) => (
                                    <option key={m} value={m}>
                                      {m}
                                    </option>
                                  ))}
                                </select>
                              </div>
                              <span className="text-xs text-muted-foreground font-mono">
                                ({cronHour}:{cronMinute} in {effectiveTimezone})
                              </span>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Hourly minute selector */}
                      {cronFrequency === "hourly" && (
                        <div className="p-3 bg-background rounded-md border border-border space-y-1.5">
                          <label className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                            <Clock className="w-3.5 h-3.5 text-primary" />
                            Run at Minute of the Hour
                          </label>
                          <div className="flex items-center gap-2">
                            <select
                              className="h-8 rounded-md border border-input bg-background px-3 text-xs font-mono cursor-pointer"
                              value={cronMinute}
                              onChange={(e) => handleMinuteChange(e.target.value)}
                            >
                              <option value="00">At :00 (top of the hour)</option>
                              <option value="15">At :15 past the hour</option>
                              <option value="30">At :30 past the hour</option>
                              <option value="45">At :45 past the hour</option>
                            </select>
                          </div>
                        </div>
                      )}

                      {/* Human-Readable Live Schedule Summary */}
                      <div className="flex items-start gap-2.5 p-3 rounded-md bg-primary/5 border border-primary/20 text-xs">
                        <Clock className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                        <div className="space-y-0.5 min-w-0">
                          <span className="font-semibold text-foreground block">
                            {getHumanReadableCron(formCron, effectiveTimezone)}
                          </span>
                          <span className="text-[11px] font-mono text-muted-foreground block">
                            Cron:{" "}
                            <span className="bg-background px-1.5 py-0.5 rounded border border-border text-foreground font-bold">
                              {formCron}
                            </span>{" "}
                            • Timezone: {effectiveTimezone}
                          </span>
                        </div>
                      </div>

                      {/* Custom Cron Input or Advanced toggle */}
                      {cronFrequency === "custom" ? (
                        <div className="space-y-1">
                          <label className="text-xs font-semibold text-foreground">
                            Custom Cron Expression *
                          </label>
                          <Input
                            value={formCron}
                            onChange={(e) => setFormCron(e.target.value)}
                            placeholder="* * * * *"
                            className="font-mono text-xs"
                            required
                          />
                          <span className="text-[11px] text-muted-foreground block font-mono">
                            Format: min (0-59) hour (0-23) dom (1-31) mon (1-12) dow (0-7)
                          </span>
                        </div>
                      ) : (
                        <div className="pt-0.5">
                          <button
                            type="button"
                            onClick={() => setShowAdvancedCron(!showAdvancedCron)}
                            className="text-[11px] text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors cursor-pointer"
                          >
                            <Sliders className="w-3 h-3" />
                            {showAdvancedCron
                              ? "Hide raw expression"
                              : "Inspect or edit raw cron syntax"}
                          </button>
                          {showAdvancedCron && (
                            <div className="mt-2 space-y-1">
                              <Input
                                value={formCron}
                                onChange={(e) => setFormCron(e.target.value)}
                                className="font-mono text-xs"
                              />
                              <span className="text-[10px] text-muted-foreground block font-mono">
                                Format: min hour dom mon dow
                              </span>
                            </div>
                          )}
                        </div>
                      )}
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
                        Interval in seconds (e.g. 60 = every minute, 300 = every 5 mins, 3600 = every hour)
                      </span>
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-muted-foreground block mb-1">
                      Misfire Policy
                    </label>
                    <select
                      className="w-full h-9 rounded-md border border-input bg-background px-3 text-xs text-foreground cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      value={formMisfire}
                      onChange={(e) => setFormMisfire(e.target.value)}
                    >
                      <option value="coalescing">Coalescing (merge missed triggers)</option>
                      <option value="skip">Skip (ignore missed triggers)</option>
                      <option value="catch_up">Catch Up (execute every missed trigger)</option>
                    </select>
                  </div>
                  <div className="flex items-center pt-2 sm:pt-6">
                    <label className="flex items-center gap-2 text-xs cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={formEnabled}
                        onChange={(e) => setFormEnabled(e.target.checked)}
                        className="rounded cursor-pointer"
                      />
                      <span className="font-medium text-foreground">Enable immediately</span>
                    </label>
                  </div>
                </div>

                {/* Task Payload (JSON) with Comprehensive Guide & Templates */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
                      Task Payload (JSON)
                    </label>
                    {isPayloadValid ? (
                      <span className="text-[11px] font-medium text-emerald-500 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Valid JSON
                      </span>
                    ) : (
                      <span className="text-[11px] font-medium text-destructive flex items-center gap-1">
                        <AlertTriangle className="w-3.5 h-3.5" /> Invalid JSON syntax
                      </span>
                    )}
                  </div>

                  {/* Guide Box */}
                  <div className="text-[11px] text-muted-foreground bg-muted/40 p-3 rounded-md border border-border space-y-2">
                    <p className="flex items-start gap-1.5">
                      <Info className="w-3.5 h-3.5 text-primary shrink-0 mt-0.5" />
                      <span>
                        Key-value arguments passed to your Python task handler function (e.g.{" "}
                        <code className="bg-background px-1 py-0.5 rounded text-foreground font-mono">
                          def send_email(recipient, subject)
                        </code>
                        ). If your task requires no arguments, leave as{" "}
                        <code className="bg-background px-1 py-0.5 rounded text-foreground font-mono">
                          {"{}"}
                        </code>
                        .
                      </span>
                    </p>

                    <div className="flex items-center gap-1.5 flex-wrap pt-1 border-t border-border/60">
                      <span className="text-[10px] font-semibold text-foreground">Insert example:</span>
                      <button
                        type="button"
                        onClick={() => insertPayloadTemplate("email")}
                        className="px-2 py-0.5 rounded bg-background hover:bg-accent hover:border-primary/40 border border-border text-[10px] text-foreground font-medium transition-colors cursor-pointer"
                      >
                        ✉️ Email Digest
                      </button>
                      <button
                        type="button"
                        onClick={() => insertPayloadTemplate("report")}
                        className="px-2 py-0.5 rounded bg-background hover:bg-accent hover:border-primary/40 border border-border text-[10px] text-foreground font-medium transition-colors cursor-pointer"
                      >
                        📊 Daily Report
                      </button>
                      <button
                        type="button"
                        onClick={() => insertPayloadTemplate("cleanup")}
                        className="px-2 py-0.5 rounded bg-background hover:bg-accent hover:border-primary/40 border border-border text-[10px] text-foreground font-medium transition-colors cursor-pointer"
                      >
                        🧹 Maintenance
                      </button>
                      <button
                        type="button"
                        onClick={() => insertPayloadTemplate("empty")}
                        className="px-2 py-0.5 rounded bg-background hover:bg-accent hover:border-primary/40 border border-border text-[10px] text-muted-foreground hover:text-foreground font-mono transition-colors cursor-pointer"
                      >
                        {"{}"}
                      </button>
                      <button
                        type="button"
                        onClick={handleFormatPayload}
                        className="ml-auto px-2 py-0.5 rounded bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 text-[10px] font-semibold transition-colors cursor-pointer flex items-center gap-1"
                      >
                        <Sparkles className="w-3 h-3" />
                        Format JSON
                      </button>
                    </div>
                  </div>

                  <textarea
                    rows={4}
                    className={cn(
                      "w-full rounded-md border bg-background px-3 py-2 text-xs font-mono text-foreground focus-visible:outline-none focus-visible:ring-1",
                      isPayloadValid
                        ? "border-input focus-visible:ring-ring"
                        : "border-destructive focus-visible:ring-destructive"
                    )}
                    value={formPayload}
                    onChange={(e) => setFormPayload(e.target.value)}
                    placeholder='{\n  "key": "value"\n}'
                  />
                </div>

                <div className="flex justify-end gap-2 pt-3 border-t border-border sticky bottom-0 bg-card py-2">
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
                    disabled={createSchedule.isPending || !isPayloadValid}
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

      <ConfirmDialog
        open={!!scheduleToDelete}
        onOpenChange={(open) => !open && setScheduleToDelete(null)}
        title="Delete Schedule"
        description={`Are you sure you want to permanently delete schedule for "${scheduleToDelete?.task_type}"? It will no longer trigger recurring tasks.`}
        confirmLabel="Delete Schedule"
        variant="destructive"
        loading={deletingSchedule}
        onConfirm={confirmDeleteSchedule}
      />
    </div>
  );
}
