"use client";

import React, { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useQueues } from "@/lib/api-hooks";
import { apiClient } from "@/lib/api-client";
import { useQueryClient } from "@tanstack/react-query";
import { Layers, Plus, Trash2, Gauge, ShieldAlert, AlertCircle } from "lucide-react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

export default function QueuesPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQueues();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [queueName, setQueueName] = useState("");
  const [brokerBackend, setBrokerBackend] = useState("native");
  const [maxConcurrency, setMaxConcurrency] = useState(100);
  const [rateLimit, setRateLimit] = useState(100);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await apiClient.post("/queues", {
        queue_name: queueName,
        broker_backend: brokerBackend,
        max_concurrency: Number(maxConcurrency),
        rate_limit_rps: Number(rateLimit),
      });
      queryClient.invalidateQueries({ queryKey: ["queues"] });
      setShowCreateModal(false);
      setQueueName("");
    } catch (err: any) {
      setError(err.message || "Failed to create queue.");
    } finally {
      setSubmitting(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    const name = deleteTarget;
    setDeleting(true);
    setDeleteError(null);
    try {
      queryClient.setQueryData(["queues"], (old: any) => {
        if (!old?.items) return old;
        return {
          ...old,
          items: old.items.filter((q: any) => q.queue_name !== name),
          total: Math.max(0, (old.total ?? old.items.length) - 1),
        };
      });
      await apiClient.delete(`/queues/${name}?force=true`);
      queryClient.invalidateQueries({ queryKey: ["queues"] });
    } catch (err: any) {
      queryClient.invalidateQueries({ queryKey: ["queues"] });
      setDeleteError(err.message || "Failed to delete queue.");
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Queue Configuration</h1>
          <p className="text-sm text-muted-foreground">
            Manage distributed task queues, rate-limits, and underlying broker adapters.
          </p>
        </div>
        <Button size="sm" onClick={() => setShowCreateModal(true)} className="gap-2">
          <Plus className="w-4 h-4" />
          Create Queue
        </Button>
      </div>

      {deleteError && (
        <div className="p-3 bg-destructive/10 border border-destructive/20 text-destructive text-xs rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{deleteError}</span>
          </div>
          <button onClick={() => setDeleteError(null)} className="text-muted-foreground hover:text-foreground">
            ✕
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {isLoading ? (
          <div className="col-span-full p-12 text-center text-sm text-muted-foreground">
            Loading queues...
          </div>
        ) : !data?.items.length ? (
          <div className="col-span-full p-12 text-center text-sm text-muted-foreground">
            No queues found.
          </div>
        ) : (
          data.items.map((q) => (
            <Card key={q.queue_name} className="flex flex-col justify-between">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Layers className="w-4 h-4 text-indigo-500" />
                    <CardTitle className="text-base font-semibold font-mono">
                      {q.queue_name}
                    </CardTitle>
                  </div>
                  <Badge variant={q.enabled ? "success" : "secondary"}>
                    {q.enabled ? "Active" : "Disabled"}
                  </Badge>
                </div>
                <CardDescription className="font-mono text-xs">
                  Backend: {q.broker_backend}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-2 text-xs font-mono bg-muted/40 p-3 rounded-lg">
                  <div>
                    <span className="text-muted-foreground">Max Concurrency:</span>
                    <p className="font-semibold text-foreground">{q.max_concurrency}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Rate Limit:</span>
                    <p className="font-semibold text-foreground">{q.rate_limit_rps || 100} RPS</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Priority:</span>
                    <p className="font-semibold text-foreground">{q.default_priority}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Created:</span>
                    <p className="font-semibold text-foreground">
                      {new Date(q.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                {q.queue_name !== "default" && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full text-destructive hover:bg-destructive/10 text-xs gap-1.5"
                    onClick={() => setDeleteTarget(q.queue_name)}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Delete Queue
                  </Button>
                )}
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <Card className="w-full max-w-md shadow-2xl">
            <CardHeader>
              <CardTitle className="text-lg">Create New Task Queue</CardTitle>
              <CardDescription>Configure a new broker channel</CardDescription>
            </CardHeader>
            <form onSubmit={handleCreate}>
              <CardContent className="space-y-4">
                {error && (
                  <div className="p-3 bg-destructive/10 border border-destructive/20 text-destructive text-xs rounded-lg">
                    {error}
                  </div>
                )}
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-muted-foreground">Queue Name *</label>
                  <Input
                    placeholder="e.g. notifications, billing"
                    value={queueName}
                    onChange={(e) => setQueueName(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-muted-foreground">Broker Backend</label>
                  <select
                    className="w-full text-xs h-9 rounded-md border border-input bg-background px-3"
                    value={brokerBackend}
                    onChange={(e) => setBrokerBackend(e.target.value)}
                  >
                    <option value="native">Native (PostgreSQL Outbox)</option>
                    <option value="redis">Redis Streams</option>
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-muted-foreground">Concurrency</label>
                    <Input
                      type="number"
                      value={maxConcurrency}
                      onChange={(e) => setMaxConcurrency(Number(e.target.value))}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-muted-foreground">Rate Limit (RPS)</label>
                    <Input
                      type="number"
                      value={rateLimit}
                      onChange={(e) => setRateLimit(Number(e.target.value))}
                    />
                  </div>
                </div>
              </CardContent>
              <div className="p-6 pt-0 flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={submitting}>
                  {submitting ? "Creating..." : "Save Queue"}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Delete Queue"
        description={`Are you sure you want to permanently delete queue '${deleteTarget}'? This action cannot be undone.`}
        confirmLabel="Delete Queue"
        variant="destructive"
        loading={deleting}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
