"use client";

import { useState } from "react";
import {
  BarChart3,
  Clock,
  Activity,
  Layers,
  Cpu,
  PieChart as PieIcon,
  RefreshCw,
  TrendingUp,
  Zap,
} from "lucide-react";
import {
  useAnalyticsThroughput,
  useAnalyticsLatency,
  useAnalyticsQueueDepth,
  useAnalyticsWorkerUtilization,
  useAnalyticsStatusDistribution,
  useQueues,
} from "@/lib/api-hooks";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BaseChart } from "@/components/charts/base-chart";
import type { EChartsCoreOption } from "echarts/core";

export default function MetricsPage() {
  const [timeRangeHours, setTimeRangeHours] = useState(24);
  const [selectedQueue, setSelectedQueue] = useState<string>("");

  const { data: queuesData } = useQueues();
  const {
    data: throughput,
    isLoading: loadingThroughput,
    refetch: refetchThroughput,
    isRefetching: refetchingThroughput,
  } = useAnalyticsThroughput(timeRangeHours);

  const {
    data: latency,
    isLoading: loadingLatency,
    refetch: refetchLatency,
  } = useAnalyticsLatency(selectedQueue || undefined);

  const {
    data: queueDepth,
    isLoading: loadingDepth,
    refetch: refetchDepth,
  } = useAnalyticsQueueDepth();

  const {
    data: workerUtil,
    isLoading: loadingWorkers,
    refetch: refetchWorkers,
  } = useAnalyticsWorkerUtilization();

  const {
    data: statusDist,
    isLoading: loadingDist,
    refetch: refetchDist,
  } = useAnalyticsStatusDistribution(selectedQueue || undefined);

  const handleRefreshAll = () => {
    refetchThroughput();
    refetchLatency();
    refetchDepth();
    refetchWorkers();
    refetchDist();
  };

  const queues = queuesData?.items || [];

  const throughputOption: EChartsCoreOption = {
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(15, 23, 42, 0.9)",
      borderColor: "#334155",
      textStyle: { color: "#f8fafc", fontSize: 12 },
    },
    legend: {
      data: ["Incoming Rate (TPS)", "Outgoing Rate (TPS)"],
      textStyle: { color: "#94a3b8" },
      top: 0,
      right: 10,
    },
    grid: {
      left: "3%",
      right: "4%",
      bottom: "10%",
      top: "15%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: (throughput?.points || []).map((p) =>
        new Date(p.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      ),
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: "#94a3b8", fontSize: 11 },
    },
    yAxis: {
      type: "value",
      name: "Tasks / sec",
      nameTextStyle: { color: "#94a3b8", fontSize: 11 },
      axisLine: { lineStyle: { color: "#334155" } },
      splitLine: { lineStyle: { color: "#1e293b" } },
      axisLabel: { color: "#94a3b8", fontSize: 11 },
    },
    series: [
      {
        name: "Incoming Rate (TPS)",
        type: "line",
        smooth: true,
        data: (throughput?.points || []).map((p) => p.incoming_rate),
        itemStyle: { color: "#3b82f6" },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(59, 130, 246, 0.35)" },
              { offset: 1, color: "rgba(59, 130, 246, 0.0)" },
            ],
          },
        },
      },
      {
        name: "Outgoing Rate (TPS)",
        type: "line",
        smooth: true,
        data: (throughput?.points || []).map((p) => p.outgoing_rate),
        itemStyle: { color: "#10b981" },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(16, 185, 129, 0.35)" },
              { offset: 1, color: "rgba(16, 185, 129, 0.0)" },
            ],
          },
        },
      },
    ],
  };

  const latencyOption: EChartsCoreOption = {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: "rgba(15, 23, 42, 0.9)",
      borderColor: "#334155",
      textStyle: { color: "#f8fafc", fontSize: 12 },
      valueFormatter: (value: unknown) => `${value ?? 0} ms`,
    },
    legend: {
      data: ["P50 (Median)", "P95", "P99"],
      textStyle: { color: "#94a3b8" },
      top: 0,
      right: 10,
    },
    grid: {
      left: "3%",
      right: "4%",
      bottom: "10%",
      top: "15%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: ["Queue Wait", "Execution Duration", "End-to-End Total"],
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: "#94a3b8", fontSize: 11 },
    },
    yAxis: {
      type: "value",
      name: "Latency (ms)",
      nameTextStyle: { color: "#94a3b8", fontSize: 11 },
      axisLine: { lineStyle: { color: "#334155" } },
      splitLine: { lineStyle: { color: "#1e293b" } },
      axisLabel: { color: "#94a3b8", fontSize: 11 },
    },
    series: [
      {
        name: "P50 (Median)",
        type: "bar",
        data: [
          latency?.queue_wait.p50_ms || 0,
          latency?.execution_duration.p50_ms || 0,
          latency?.e2e_duration.p50_ms || 0,
        ],
        itemStyle: { color: "#60a5fa" },
      },
      {
        name: "P95",
        type: "bar",
        data: [
          latency?.queue_wait.p95_ms || 0,
          latency?.execution_duration.p95_ms || 0,
          latency?.e2e_duration.p95_ms || 0,
        ],
        itemStyle: { color: "#f59e0b" },
      },
      {
        name: "P99",
        type: "bar",
        data: [
          latency?.queue_wait.p99_ms || 0,
          latency?.execution_duration.p99_ms || 0,
          latency?.e2e_duration.p99_ms || 0,
        ],
        itemStyle: { color: "#ef4444" },
      },
    ],
  };

  // 3. Status Distribution Donut Chart
  const statusColorMap: Record<string, string> = {
    SUCCEEDED: "#10b981",
    RUNNING: "#3b82f6",
    QUEUED: "#8b5cf6",
    RETRY_WAIT: "#f59e0b",
    FAILED: "#ef4444",
    DEAD: "#64748b",
    TIMED_OUT: "#ec4899",
    CANCELLED: "#94a3b8",
    SCHEDULED: "#06b6d4",
    PENDING: "#a855f7",
  };

  const statusDonutOption: EChartsCoreOption = {
    tooltip: {
      trigger: "item",
      formatter: "{b}: {c} tasks ({d}%)",
      backgroundColor: "rgba(15, 23, 42, 0.9)",
      borderColor: "#334155",
      textStyle: { color: "#f8fafc", fontSize: 12 },
    },
    legend: {
      orient: "vertical",
      right: 10,
      top: "center",
      textStyle: { color: "#94a3b8", fontSize: 11 },
    },
    series: [
      {
        name: "Status Distribution",
        type: "pie",
        radius: ["48%", "72%"],
        center: ["40%", "50%"],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: "#0f172a",
          borderWidth: 2,
        },
        label: {
          show: false,
          position: "center",
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: "bold",
            color: "#f8fafc",
          },
        },
        data: (statusDist?.distribution || []).map((item) => ({
          name: item.status,
          value: item.count,
          itemStyle: { color: statusColorMap[item.status] || "#64748b" },
        })),
      },
    ],
  };

  // 4. Queue Depth Chart
  const depthPoints = queueDepth?.queues || [];
  const queueDepthOption: EChartsCoreOption = {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: "rgba(15, 23, 42, 0.9)",
      borderColor: "#334155",
      textStyle: { color: "#f8fafc", fontSize: 12 },
    },
    grid: {
      left: "3%",
      right: "4%",
      bottom: "10%",
      top: "15%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: depthPoints.map((q) => q.queue_name),
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: "#94a3b8", fontSize: 11 },
    },
    yAxis: [
      {
        type: "value",
        name: "Backlog Tasks",
        nameTextStyle: { color: "#94a3b8", fontSize: 11 },
        axisLine: { lineStyle: { color: "#334155" } },
        splitLine: { lineStyle: { color: "#1e293b" } },
        axisLabel: { color: "#94a3b8", fontSize: 11 },
      },
    ],
    series: [
      {
        name: "Backlog Depth",
        type: "bar",
        data: depthPoints.map((q) => q.depth),
        itemStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "#8b5cf6" },
              { offset: 1, color: "#6366f1" },
            ],
          },
        },
      },
    ],
  };

  // 5. Worker Utilization Bar Chart
  const workers = workerUtil?.workers || [];
  const workerUtilOption: EChartsCoreOption = {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: "rgba(15, 23, 42, 0.9)",
      borderColor: "#334155",
      textStyle: { color: "#f8fafc", fontSize: 12 },
      valueFormatter: (value: unknown) => `${value ?? 0}%`,
    },
    grid: {
      left: "3%",
      right: "4%",
      bottom: "15%",
      top: "10%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: workers.map((w) => w.hostname || w.worker_id.slice(0, 8)),
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: "#94a3b8", fontSize: 10, rotate: 20 },
    },
    yAxis: {
      type: "value",
      name: "Capacity Utilization %",
      max: 100,
      nameTextStyle: { color: "#94a3b8", fontSize: 11 },
      axisLine: { lineStyle: { color: "#334155" } },
      splitLine: { lineStyle: { color: "#1e293b" } },
      axisLabel: { color: "#94a3b8", fontSize: 11 },
    },
    series: [
      {
        name: "Slot Utilization",
        type: "bar",
        data: workers.map((w) => w.utilization_percent),
        itemStyle: {
          color: (params: { value: unknown }) => {
            const v = Number(params.value);
            if (v >= 90) return "#ef4444";
            if (v >= 70) return "#f59e0b";
            return "#10b981";
          },
        },
      },
    ],
  };

  return (
    <div className="space-y-6">
      {/* Top Banner / Time Horizon Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-primary" />
            Telemetry & Analytics
          </h1>
          <p className="text-sm text-muted-foreground">
            Grafana-grade real-time system metrics, latency percentiles, and cluster load telemetry.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Queue Filter */}
          <select
            className="h-8 rounded-md border border-input bg-background px-2.5 text-xs text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            value={selectedQueue}
            onChange={(e) => setSelectedQueue(e.target.value)}
          >
            <option value="">All Queues</option>
            {queues.map((q) => (
              <option key={q.queue_name} value={q.queue_name}>
                Queue: {q.queue_name}
              </option>
            ))}
          </select>

          {/* Time Horizon Selector */}
          <div className="flex rounded-md border border-border bg-card p-0.5 text-xs">
            {[1, 6, 24, 72, 168].map((h) => (
              <button
                key={h}
                onClick={() => setTimeRangeHours(h)}
                className={`px-2.5 py-1 rounded transition-colors ${
                  timeRangeHours === h
                    ? "bg-primary text-primary-foreground font-semibold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {h === 1 ? "1h" : h === 6 ? "6h" : h === 24 ? "24h" : h === 72 ? "3d" : "7d"}
              </button>
            ))}
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={handleRefreshAll}
            disabled={refetchingThroughput}
            className="gap-1.5 h-8 text-xs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refetchingThroughput ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* KPI Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-border">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <span className="text-xs text-muted-foreground font-medium uppercase">
                Incoming Ingestion
              </span>
              <div className="text-2xl font-bold font-mono text-primary mt-1">
                {throughput?.current_incoming_tps ?? 0}{" "}
                <span className="text-xs font-normal text-muted-foreground">tasks/s</span>
              </div>
            </div>
            <Zap className="h-8 w-8 text-primary/30" />
          </CardContent>
        </Card>

        <Card className="border-border">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <span className="text-xs text-muted-foreground font-medium uppercase">
                Outgoing Throughput
              </span>
              <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
                {throughput?.current_outgoing_tps ?? 0}{" "}
                <span className="text-xs font-normal text-muted-foreground">tasks/s</span>
              </div>
            </div>
            <TrendingUp className="h-8 w-8 text-emerald-500/30" />
          </CardContent>
        </Card>

        <Card className="border-border">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <span className="text-xs text-muted-foreground font-medium uppercase">
                End-to-End P99 Latency
              </span>
              <div className="text-2xl font-bold font-mono text-foreground mt-1">
                {latency?.e2e_duration.p99_ms ?? 0}{" "}
                <span className="text-xs font-normal text-muted-foreground">ms</span>
              </div>
            </div>
            <Clock className="h-8 w-8 text-amber-500/30" />
          </CardContent>
        </Card>

        <Card className="border-border">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <span className="text-xs text-muted-foreground font-medium uppercase">
                Avg Cluster Slot Load
              </span>
              <div className="text-2xl font-bold font-mono text-foreground mt-1">
                {workerUtil?.average_utilization_percent ?? 0}
                <span className="text-xs font-normal text-muted-foreground">%</span>
              </div>
            </div>
            <Cpu className="h-8 w-8 text-purple-500/30" />
          </CardContent>
        </Card>
      </div>

      {/* Primary Charts: Throughput & Latency */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Throughput */}
        <Card className="border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" />
              Throughput Velocity (Incoming vs Outgoing TPS)
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-2">
            <BaseChart
              options={throughputOption}
              height="300px"
              loading={loadingThroughput}
            />
          </CardContent>
        </Card>

        {/* Latency Percentiles */}
        <Card className="border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Clock className="h-4 w-4 text-amber-400" />
              Latency Percentiles (Queue Wait vs Execution) (SRS §17.19)
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-2">
            <BaseChart
              options={latencyOption}
              height="300px"
              loading={loadingLatency}
            />
          </CardContent>
        </Card>
      </div>

      {/* Secondary Charts: Status Distribution & Queue Depth & Worker Utilization */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Status Breakdown Donut */}
        <Card className="border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <PieIcon className="h-4 w-4 text-indigo-400" />
              Task Status Distribution
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-2">
            {statusDist && statusDist.total_tasks > 0 ? (
              <BaseChart
                options={statusDonutOption}
                height="280px"
                loading={loadingDist}
              />
            ) : (
              <div className="h-[280px] flex items-center justify-center text-xs text-muted-foreground">
                No task history recorded in this window
              </div>
            )}
          </CardContent>
        </Card>

        {/* Queue Depth Backlog */}
        <Card className="border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Layers className="h-4 w-4 text-purple-400" />
              Queue Depth Backlog
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-2">
            {depthPoints.length > 0 ? (
              <BaseChart
                options={queueDepthOption}
                height="280px"
                loading={loadingDepth}
              />
            ) : (
              <div className="h-[280px] flex items-center justify-center text-xs text-muted-foreground">
                All queues are currently empty (0 backlog)
              </div>
            )}
          </CardContent>
        </Card>

        {/* Worker Slot Utilization */}
        <Card className="border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Cpu className="h-4 w-4 text-emerald-400" />
              Worker Slot Capacity Utilization
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-2">
            {workers.length > 0 ? (
              <BaseChart
                options={workerUtilOption}
                height="280px"
                loading={loadingWorkers}
              />
            ) : (
              <div className="h-[280px] flex items-center justify-center text-xs text-muted-foreground">
                No active worker instances online
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
