"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Skull,
  RotateCcw,
  Trash2,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  X,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Layers,
  FileCode,
} from "lucide-react";
import {
  useDLQ,
  useReplayDLQ,
  useBulkReplayDLQ,
  useDiscardDLQ,
} from "@/lib/api-hooks";
import { DLQItem } from "@/types/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function DLQPage() {
  const [pageLimit] = useState(25);
  const [pageOffset, setPageOffset] = useState(0);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [detailItem, setDetailItem] = useState<DLQItem | null>(null);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(
    null
  );

  const { data: dlqData, isLoading, refetch, isRefetching } = useDLQ(pageLimit, pageOffset);
  const replayDLQ = useReplayDLQ();
  const bulkReplayDLQ = useBulkReplayDLQ();
  const discardDLQ = useDiscardDLQ();

  const items = dlqData?.items || [];
  const total = dlqData?.total || 0;

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(items.map((i) => i.dlq_id));
    } else {
      setSelectedIds([]);
    }
  };

  const handleToggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const handleSingleReplay = async (item: DLQItem) => {
    setFeedback(null);
    try {
      await replayDLQ.mutateAsync(item.dlq_id);
      setSelectedIds((prev) => prev.filter((id) => id !== item.dlq_id));
      setFeedback({
        type: "success",
        message: `Task ${item.task_id} successfully replayed into active queue.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to replay task";
      setFeedback({ type: "error", message: msg });
    }
  };

  const handleBulkReplaySelected = async () => {
    if (selectedIds.length === 0) return;
    setFeedback(null);
    try {
      const res = await bulkReplayDLQ.mutateAsync(selectedIds);
      setSelectedIds([]);
      setFeedback({
        type: "success",
        message: `Successfully replayed ${res.replayed_count} tasks back into active queues.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to bulk replay tasks";
      setFeedback({ type: "error", message: msg });
    }
  };

  const handleBulkReplayAll = async () => {
    if (!confirm(`Are you sure you want to replay up to 100 dead-lettered tasks?`)) return;
    setFeedback(null);
    try {
      const res = await bulkReplayDLQ.mutateAsync(undefined);
      setSelectedIds([]);
      setFeedback({
        type: "success",
        message: `Successfully replayed ${res.replayed_count} dead tasks back into queues.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to bulk replay tasks";
      setFeedback({ type: "error", message: msg });
    }
  };

  const handleDiscard = async (item: DLQItem) => {
    if (!confirm(`Permanently discard DLQ entry for task ${item.task_id}?`)) return;
    setFeedback(null);
    try {
      await discardDLQ.mutateAsync(item.dlq_id);
      setSelectedIds((prev) => prev.filter((id) => id !== item.dlq_id));
      if (detailItem?.dlq_id === item.dlq_id) setDetailItem(null);
      setFeedback({
        type: "success",
        message: "DLQ entry discarded.",
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to discard DLQ entry";
      setFeedback({ type: "error", message: msg });
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner / Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Skull className="h-6 w-6 text-destructive" />
            Dead Letter Queue (DLQ)
          </h1>
          <p className="text-sm text-muted-foreground">
            Poison messages and unrecoverable tasks isolated for root-cause analysis and manual replay.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
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

          {selectedIds.length > 0 && (
            <Button
              size="sm"
              onClick={handleBulkReplaySelected}
              disabled={bulkReplayDLQ.isPending}
              className="gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              <RotateCcw className="h-4 w-4" />
              Replay Selected ({selectedIds.length})
            </Button>
          )}

          {total > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleBulkReplayAll}
              disabled={bulkReplayDLQ.isPending}
              className="gap-1.5 text-amber-400 border-amber-500/30 hover:bg-amber-500/10"
            >
              <Layers className="h-4 w-4" />
              Replay Top 100
            </Button>
          )}
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

      {/* Stats Summary Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="border-border">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <span className="text-xs text-muted-foreground font-medium uppercase">
                Dead Tasks Count
              </span>
              <div className="text-2xl font-bold font-mono text-destructive mt-0.5">
                {total}
              </div>
            </div>
            <Skull className="h-8 w-8 text-destructive/30" />
          </CardContent>
        </Card>

        <Card className="border-border">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <span className="text-xs text-muted-foreground font-medium uppercase">
                Selected for Replay
              </span>
              <div className="text-2xl font-bold font-mono text-foreground mt-0.5">
                {selectedIds.length}
              </div>
            </div>
            <RotateCcw className="h-8 w-8 text-primary/30" />
          </CardContent>
        </Card>

        <Card className="border-border">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <span className="text-xs text-muted-foreground font-medium uppercase">
                Isolation Policy
              </span>
              <div className="text-sm font-semibold text-foreground mt-1">
                Max Retries Exceeded / Permanent
              </div>
            </div>
            <AlertTriangle className="h-8 w-8 text-amber-500/30" />
          </CardContent>
        </Card>
      </div>

      {/* DLQ Table */}
      <Card className="border-border overflow-hidden">
        <CardHeader className="p-4 border-b border-border flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Skull className="h-4 w-4 text-destructive" />
            Poison Message Roster ({total} items)
          </CardTitle>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>
              Showing {items.length > 0 ? pageOffset + 1 : 0} -{" "}
              {Math.min(pageOffset + items.length, total)} of {total}
            </span>
          </div>
        </CardHeader>

        {isLoading ? (
          <div className="p-12 text-center text-sm text-muted-foreground animate-pulse">
            Loading dead-lettered entries...
          </div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <CheckCircle2 className="h-10 w-10 text-emerald-500 mx-auto" />
            <div className="text-base font-semibold text-foreground">
              Dead Letter Queue is Clean
            </div>
            <p className="text-sm text-muted-foreground max-w-sm mx-auto">
              No failed tasks are currently isolated in the DLQ. All workflows are operating normally.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-muted/40 text-muted-foreground border-b border-border">
                  <th className="p-3 w-10">
                    <input
                      type="checkbox"
                      checked={items.length > 0 && selectedIds.length === items.length}
                      onChange={(e) => handleSelectAll(e.target.checked)}
                      className="rounded"
                    />
                  </th>
                  <th className="p-3 font-medium">Task ID</th>
                  <th className="p-3 font-medium">Queue</th>
                  <th className="p-3 font-medium">Error Class</th>
                  <th className="p-3 font-medium">Reason</th>
                  <th className="p-3 font-medium">Dead At</th>
                  <th className="p-3 font-medium">Replays</th>
                  <th className="p-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((item) => {
                  const isSelected = selectedIds.includes(item.dlq_id);
                  return (
                    <tr
                      key={item.dlq_id}
                      className={`hover:bg-muted/30 transition-colors ${
                        isSelected ? "bg-primary/5" : ""
                      }`}
                    >
                      <td className="p-3">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleToggleSelect(item.dlq_id)}
                          className="rounded"
                        />
                      </td>

                      <td className="p-3 font-mono font-medium">
                        <Link
                          href={`/tasks/${item.task_id}`}
                          className="text-primary hover:underline flex items-center gap-1"
                        >
                          {item.task_id.slice(0, 8)}...
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      </td>

                      <td className="p-3">
                        <Badge variant="outline" className="font-mono text-[11px]">
                          {item.queue || "default"}
                        </Badge>
                      </td>

                      <td className="p-3 font-mono text-destructive font-semibold">
                        {item.error_class || "FatalException"}
                      </td>

                      <td className="p-3 max-w-xs truncate text-muted-foreground" title={item.reason}>
                        {item.reason}
                      </td>

                      <td className="p-3 text-muted-foreground whitespace-nowrap">
                        {new Date(item.dead_at).toLocaleString()}
                      </td>

                      <td className="p-3 font-mono">
                        <span
                          className={
                            item.replay_count > 0 ? "text-amber-400 font-semibold" : "text-muted-foreground"
                          }
                        >
                          {item.replay_count}
                        </span>
                      </td>

                      <td className="p-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setDetailItem(item)}
                            title="Inspect error payload and traceback"
                            className="h-7 px-2 text-xs"
                          >
                            <FileCode className="h-3.5 w-3.5" />
                          </Button>

                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleSingleReplay(item)}
                            disabled={replayDLQ.isPending}
                            title="Replay this task into queue"
                            className="h-7 px-2 text-xs text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/10"
                          >
                            <RotateCcw className="h-3.5 w-3.5 mr-1" />
                            Replay
                          </Button>

                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDiscard(item)}
                            disabled={discardDLQ.isPending}
                            title="Permanently remove from DLQ"
                            className="h-7 px-2 text-xs text-destructive hover:bg-destructive/10"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination controls */}
        {total > pageLimit && (
          <div className="p-3 border-t border-border flex items-center justify-between text-xs">
            <span className="text-muted-foreground">
              Page {Math.floor(pageOffset / pageLimit) + 1} of{" "}
              {Math.ceil(total / pageLimit)}
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                disabled={pageOffset === 0}
                onClick={() => setPageOffset((prev) => Math.max(0, prev - pageLimit))}
                className="h-7 px-2"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={pageOffset + pageLimit >= total}
                onClick={() => setPageOffset((prev) => prev + pageLimit)}
                className="h-7 px-2"
              >
                Next
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Error Details Modal */}
      {detailItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
          <Card className="w-full max-w-2xl max-h-[85vh] overflow-y-auto border-border shadow-2xl">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-lg font-bold flex items-center gap-2 text-destructive">
                <Skull className="h-5 w-5" />
                DLQ Error Details: {detailItem.error_class}
              </CardTitle>
              <button
                onClick={() => setDetailItem(null)}
                className="text-muted-foreground hover:text-foreground p-1"
              >
                <X className="h-5 w-5" />
              </button>
            </CardHeader>
            <CardContent className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-2.5 rounded bg-muted/50 border border-border">
                  <span className="text-muted-foreground block mb-1">Task ID</span>
                  <Link
                    href={`/tasks/${detailItem.task_id}`}
                    className="font-mono text-primary hover:underline break-all"
                  >
                    {detailItem.task_id}
                  </Link>
                </div>
                <div className="p-2.5 rounded bg-muted/50 border border-border">
                  <span className="text-muted-foreground block mb-1">Queue</span>
                  <span className="font-mono font-semibold text-foreground">
                    {detailItem.queue || "default"}
                  </span>
                </div>
                <div className="p-2.5 rounded bg-muted/50 border border-border">
                  <span className="text-muted-foreground block mb-1">Isolated At</span>
                  <span className="text-foreground">
                    {new Date(detailItem.dead_at).toLocaleString()}
                  </span>
                </div>
                <div className="p-2.5 rounded bg-muted/50 border border-border">
                  <span className="text-muted-foreground block mb-1">Replay Count</span>
                  <span className="font-mono text-foreground font-semibold">
                    {detailItem.replay_count} times
                  </span>
                </div>
              </div>

              <div>
                <span className="font-medium text-muted-foreground block mb-1.5">
                  Failure Reason / Traceback Summary
                </span>
                <pre className="p-3 bg-destructive/10 border border-destructive/20 rounded-md font-mono text-destructive whitespace-pre-wrap overflow-x-auto text-[11px]">
                  {detailItem.reason || "No failure description recorded."}
                </pre>
              </div>

              {detailItem.payload_ref && (
                <div>
                  <span className="font-medium text-muted-foreground block mb-1.5">
                    Payload Storage Reference
                  </span>
                  <code className="p-2 block bg-muted/50 rounded border border-border font-mono text-muted-foreground break-all">
                    {detailItem.payload_ref}
                  </code>
                </div>
              )}

              <div className="flex justify-between items-center pt-3 border-t border-border">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDiscard(detailItem)}
                  className="text-destructive hover:bg-destructive/10 border-destructive/30"
                >
                  <Trash2 className="h-3.5 w-3.5 mr-1" />
                  Discard Entry
                </Button>

                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setDetailItem(null)}
                  >
                    Close
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => {
                      handleSingleReplay(detailItem);
                      setDetailItem(null);
                    }}
                    className="gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    Replay Task
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
