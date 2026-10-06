import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import {
  Task,
  TaskDetail,
  PaginatedResponse,
  QueueItem,
  QueueDepth,
  WorkerItem,
  ScheduleItem,
  DLQItem,
  ThroughputData,
  LatencyData,
  QueueDepthPoint,
  WorkerUtilizationData,
  StatusDistributionData,
  User,
} from "@/types/api";

export const queryKeys = {
  tasks: (filters?: Record<string, unknown>) => ["tasks", filters],
  taskDetail: (id: string) => ["tasks", "detail", id],
  queues: () => ["queues"],
  queueDepth: (name: string) => ["queues", "depth", name],
  workers: (status?: string) => ["workers", status],
  schedules: () => ["schedules"],
  dlq: () => ["dlq"],
  throughput: (hours: number) => ["analytics", "throughput", hours],
  latency: (queue?: string) => ["analytics", "latency", queue],
  queueDepthTrend: () => ["analytics", "queue-depth"],
  workerUtilization: () => ["analytics", "worker-utilization"],
  statusDistribution: (queue?: string) => ["analytics", "status-distribution", queue],
};

export function useTasks(params: {
  queue?: string;
  status?: string;
  limit?: number;
  offset?: number;
} = {}) {
  const queryParams = new URLSearchParams();
  if (params.queue) queryParams.set("queue", params.queue);
  if (params.status) queryParams.set("status", params.status);
  if (params.limit) queryParams.set("limit", params.limit.toString());
  if (params.offset !== undefined) queryParams.set("offset", params.offset.toString());

  return useQuery({
    queryKey: queryKeys.tasks(params),
    queryFn: () =>
      apiClient.get<PaginatedResponse<Task>>(
        `/tasks?${queryParams.toString()}`
      ),
    refetchInterval: 8000,
  });
}

export function useTaskDetail(taskId: string) {
  return useQuery({
    queryKey: queryKeys.taskDetail(taskId),
    queryFn: () => apiClient.get<TaskDetail>(`/tasks/${taskId}`),
    enabled: !!taskId,
    refetchInterval: 8000,
  });
}

export function useSubmitTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      task_type: string;
      queue?: string;
      priority?: number;
      payload?: Record<string, unknown>;
      idempotency_key?: string;
    }) => apiClient.post<Task>("/tasks", body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: queryKeys.queues() });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

export function useCancelTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => apiClient.delete<Task>(`/tasks/${taskId}`),
    onSuccess: (_, taskId) => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: queryKeys.taskDetail(taskId) });
    },
  });
}

export function useRetryTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => apiClient.post<Task>(`/tasks/${taskId}/retry`),
    onSuccess: (_, taskId) => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: queryKeys.taskDetail(taskId) });
    },
  });
}

// Queues
export function useQueues() {
  return useQuery({
    queryKey: queryKeys.queues(),
    queryFn: () => apiClient.get<PaginatedResponse<QueueItem>>("/queues"),
    refetchInterval: 10000,
  });
}

export function useQueueDepth(name: string) {
  return useQuery({
    queryKey: queryKeys.queueDepth(name),
    queryFn: () => apiClient.get<QueueDepth>(`/queues/${name}/depth`),
    enabled: !!name,
    refetchInterval: 8000,
  });
}

export function useCreateQueue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      queue_name: string;
      enabled?: boolean;
      default_priority?: number;
      max_concurrency?: number;
      rate_limit_rps?: number;
      broker_backend?: string;
    }) => apiClient.post<QueueItem>("/queues", body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.queues() });
    },
  });
}

export function useUpdateQueue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      queueName,
      body,
    }: {
      queueName: string;
      body: {
        enabled?: boolean;
        default_priority?: number;
        max_concurrency?: number;
        rate_limit_rps?: number;
        broker_backend?: string;
      };
    }) => apiClient.put<QueueItem>(`/queues/${queueName}`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.queues() });
    },
  });
}

export function useDeleteQueue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      queueName,
      force = false,
    }: {
      queueName: string;
      force?: boolean;
    }) => apiClient.delete(`/queues/${queueName}${force ? "?force=true" : ""}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.queues() });
    },
  });
}

// Workers
export function useWorkers(status?: string) {
  const url = status ? `/workers?status=${status}` : "/workers";
  return useQuery({
    queryKey: queryKeys.workers(status),
    queryFn: () => apiClient.get<PaginatedResponse<WorkerItem>>(url),
    refetchInterval: 8000,
  });
}

export function useDrainWorker() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (workerId: string) =>
      apiClient.post<WorkerItem>(`/workers/${workerId}/drain`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workers"] });
    },
  });
}

// Schedules
export function useSchedules(enabledOnly = false) {
  const url = enabledOnly ? "/schedules?enabled_only=true" : "/schedules";
  return useQuery({
    queryKey: [...queryKeys.schedules(), enabledOnly],
    queryFn: () => apiClient.get<PaginatedResponse<ScheduleItem>>(url),
    refetchInterval: 10000,
  });
}

export function useCreateSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      task_type: string;
      queue?: string;
      cron?: string;
      interval_seconds?: number;
      timezone?: string;
      misfire_policy?: string;
      enabled?: boolean;
      payload?: Record<string, unknown>;
    }) => apiClient.post<ScheduleItem>("/schedules", body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

export function useUpdateSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      scheduleId,
      body,
    }: {
      scheduleId: string;
      body: {
        cron?: string;
        interval_seconds?: number;
        timezone?: string;
        misfire_policy?: string;
        enabled?: boolean;
        payload?: Record<string, unknown>;
      };
    }) => apiClient.put<ScheduleItem>(`/schedules/${scheduleId}`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

export function useDeleteSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (scheduleId: string) => apiClient.delete(`/schedules/${scheduleId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

export function useTriggerSchedule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (scheduleId: string) =>
      apiClient.post<Task>(`/schedules/${scheduleId}/trigger`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

// DLQ
export function useDLQ(limit = 50, offset = 0) {
  return useQuery({
    queryKey: [...queryKeys.dlq(), limit, offset],
    queryFn: () => apiClient.get<PaginatedResponse<DLQItem>>(`/dlq?limit=${limit}&offset=${offset}`),
    refetchInterval: 10000,
  });
}

export function useReplayDLQ() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dlqId: string) => apiClient.post(`/dlq/${dlqId}/replay`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dlq"] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}

export function useBulkReplayDLQ() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dlqIds?: string[]) =>
      apiClient.post<{ replayed_count: number }>("/dlq/replay/bulk", {
        dlq_ids: dlqIds,
        max_count: 100,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dlq"] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}

export function useDiscardDLQ() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dlqId: string) => apiClient.delete(`/dlq/${dlqId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dlq"] });
    },
  });
}

// Analytics
export function useAnalyticsThroughput(hours = 24) {
  return useQuery({
    queryKey: queryKeys.throughput(hours),
    queryFn: () =>
      apiClient.get<ThroughputData>(`/analytics/throughput?hours=${hours}`),
    refetchInterval: 15000,
  });
}

export function useAnalyticsLatency(queue?: string) {
  const url = queue ? `/analytics/latency?queue=${queue}` : "/analytics/latency";
  return useQuery({
    queryKey: queryKeys.latency(queue),
    queryFn: () => apiClient.get<LatencyData>(url),
    refetchInterval: 15000,
  });
}

export function useAnalyticsQueueDepth() {
  return useQuery({
    queryKey: queryKeys.queueDepthTrend(),
    queryFn: () =>
      apiClient.get<{ queues: QueueDepthPoint[] }>("/analytics/queue-depth"),
    refetchInterval: 15000,
  });
}

export function useAnalyticsWorkerUtilization() {
  return useQuery({
    queryKey: queryKeys.workerUtilization(),
    queryFn: () =>
      apiClient.get<WorkerUtilizationData>("/analytics/worker-utilization"),
    refetchInterval: 15000,
  });
}

export function useAnalyticsStatusDistribution(queue?: string) {
  const url = queue
    ? `/analytics/status-distribution?queue=${queue}`
    : "/analytics/status-distribution";
  return useQuery({
    queryKey: queryKeys.statusDistribution(queue),
    queryFn: () => apiClient.get<StatusDistributionData>(url),
    refetchInterval: 15000,
  });
}

// Authentication
export function useCurrentUser() {
  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => apiClient.get<User>("/auth/me"),
    retry: false,
    staleTime: 60000,
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post("/auth/logout"),
    onSuccess: () => {
      queryClient.clear();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    },
  });
}

