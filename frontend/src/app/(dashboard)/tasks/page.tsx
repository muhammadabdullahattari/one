"use client";

import React, { useState, useRef } from "react";
import Link from "next/link";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useTasks } from "@/lib/api-hooks";
import { TaskStatusBadge } from "@/components/task/task-status-badge";
import { TaskStatus } from "@/types/api";
import { Filter, ArrowUpDown, RefreshCw, Eye } from "lucide-react";

export default function TasksPage() {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [queueFilter, setQueueFilter] = useState<string>("");
  const [offset, setOffset] = useState<number>(0);
  const limit = 50;

  const { data, isLoading, refetch } = useTasks({
    status: statusFilter || undefined,
    queue: queueFilter || undefined,
    limit,
    offset,
  });

  const parentRef = useRef<HTMLDivElement>(null);
  const tasks = data?.items || [];

  const rowVirtualizer = useVirtualizer({
    count: tasks.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 64,
    overscan: 5,
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Task Backlog</h1>
          <p className="text-sm text-muted-foreground">
            DOM-virtualized high-concurrency execution ledger supporting 10,000+ tasks at 60 FPS.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()} className="gap-2">
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh Stream
        </Button>
      </div>

      {/* Filter Toolbar */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-xs font-semibold text-muted-foreground block mb-1">
              Filter Status
            </label>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setOffset(0);
              }}
              className="w-full text-xs h-9 rounded-md border border-input bg-background px-3"
            >
              <option value="">All Statuses</option>
              <option value="PENDING">PENDING</option>
              <option value="QUEUED">QUEUED</option>
              <option value="RUNNING">RUNNING</option>
              <option value="SUCCEEDED">SUCCEEDED</option>
              <option value="RETRY_WAIT">RETRY_WAIT</option>
              <option value="FAILED">FAILED</option>
              <option value="DEAD">DEAD</option>
              <option value="TIMED_OUT">TIMED_OUT</option>
              <option value="CANCELLED">CANCELLED</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold text-muted-foreground block mb-1">
              Filter Queue
            </label>
            <Input
              placeholder="e.g. default, reports"
              value={queueFilter}
              onChange={(e) => {
                setQueueFilter(e.target.value);
                setOffset(0);
              }}
              className="h-9 text-xs"
            />
          </div>
          <div className="flex items-end">
            <Button
              variant="secondary"
              className="w-full text-xs h-9"
              onClick={() => {
                setStatusFilter("");
                setQueueFilter("");
                setOffset(0);
              }}
            >
              Reset Filters
            </Button>
          </div>
        </div>
      </Card>

      {/* Virtualized Task Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between py-3 border-b border-border">
          <CardTitle className="text-sm font-semibold">
            Tasks Total: {data?.total || 0}
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - limit))}
            >
              Previous
            </Button>
            <span className="text-xs font-mono text-muted-foreground">
              Offset {offset} - {offset + tasks.length}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={!data?.has_more}
              onClick={() => setOffset(offset + limit)}
            >
              Next
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="grid grid-cols-12 px-4 py-2 text-xs font-semibold text-muted-foreground bg-muted/30 border-b border-border font-mono">
            <div className="col-span-4">TASK IDENTIFIER / TYPE</div>
            <div className="col-span-2">QUEUE</div>
            <div className="col-span-4">LIFECYCLE STATUS & EXPLANATION</div>
            <div className="col-span-2 text-right">DETAILS</div>
          </div>

          {isLoading ? (
            <div className="p-12 text-center text-sm text-muted-foreground">
              Virtualizing and fetching backlog rows...
            </div>
          ) : tasks.length === 0 ? (
            <div className="p-12 text-center text-sm text-muted-foreground">
              No tasks match the active filters.
            </div>
          ) : (
            <div
              ref={parentRef}
              className="h-[520px] overflow-auto relative contain-strict"
            >
              <div
                style={{
                  height: `${rowVirtualizer.getTotalSize()}px`,
                  width: "100%",
                  position: "relative",
                }}
              >
                {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                  const task = tasks[virtualRow.index];
                  return (
                    <div
                      key={task.task_id}
                      style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        width: "100%",
                        height: `${virtualRow.size}px`,
                        transform: `translateY(${virtualRow.start}px)`,
                      }}
                      className="grid grid-cols-12 px-4 py-3 items-center border-b border-border hover:bg-muted/30 transition-colors text-xs"
                    >
                      <div className="col-span-4 space-y-0.5">
                        <Link
                          href={`/tasks/${task.task_id}`}
                          className="font-medium text-foreground hover:underline block truncate"
                        >
                          {task.task_type}
                        </Link>
                        <p className="font-mono text-[10px] text-muted-foreground truncate">
                          {task.task_id}
                        </p>
                      </div>
                      <div className="col-span-2 font-mono text-muted-foreground truncate">
                        {task.queue}
                      </div>
                      <div className="col-span-4 pr-2">
                        <TaskStatusBadge task={task} showReason={true} />
                      </div>
                      <div className="col-span-2 text-right">
                        <Link href={`/tasks/${task.task_id}`}>
                          <Button variant="ghost" size="sm" className="h-7 px-2">
                            <Eye className="w-3.5 h-3.5 mr-1" />
                            Inspect
                          </Button>
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
