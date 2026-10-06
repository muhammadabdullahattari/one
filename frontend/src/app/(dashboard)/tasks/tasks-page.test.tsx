import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TasksPage from "./page";
import * as apiHooks from "@/lib/api-hooks";
import { TaskStatus } from "@/types/api";

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: vi.fn(({ count, estimateSize }) => ({
    getTotalSize: () => count * (estimateSize ? estimateSize() : 64),
    getVirtualItems: () =>
      Array.from({ length: count }, (_, index) => ({
        index,
        start: index * 64,
        size: 64,
        key: index,
      })),
  })),
}));

vi.mock("@/lib/api-hooks", () => ({
  useTasks: vi.fn(),
}));

const mockTasksData = {
  items: [
    {
      task_id: "task-001",
      task_type: "email.send_welcome",
      queue: "high-priority",
      status: "SUCCEEDED" as TaskStatus,
      status_reason: "Delivered in 240ms",
      created_at: "2026-10-02T10:00:00Z",
      updated_at: "2026-10-02T10:00:01Z",
      retries: 0,
      max_retries: 3,
    },
    {
      task_id: "task-002",
      task_type: "report.generate_pdf",
      queue: "reports",
      status: "RUNNING" as TaskStatus,
      status_reason: null,
      created_at: "2026-10-02T10:05:00Z",
      updated_at: "2026-10-02T10:05:10Z",
      retries: 1,
      max_retries: 3,
    },
  ],
  total: 2,
  offset: 0,
  limit: 50,
  has_more: false,
};

describe("TasksPage virtualized backlog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state while fetching backlog data", () => {
    (apiHooks.useTasks as any).mockReturnValue({
      data: null,
      isLoading: true,
      refetch: vi.fn(),
    });

    render(<TasksPage />);

    expect(screen.getByText(/Virtualizing and fetching backlog rows.../i)).toBeInTheDocument();
  });

  it("shows empty state when no tasks match filter criteria", () => {
    (apiHooks.useTasks as any).mockReturnValue({
      data: { items: [], total: 0, has_more: false },
      isLoading: false,
      refetch: vi.fn(),
    });

    render(<TasksPage />);

    expect(screen.getByText(/No tasks match the active filters/i)).toBeInTheDocument();
  });

  it("renders virtualized task rows when data is present", () => {
    (apiHooks.useTasks as any).mockReturnValue({
      data: mockTasksData,
      isLoading: false,
      refetch: vi.fn(),
    });

    render(<TasksPage />);

    expect(screen.getByText("Tasks Total: 2")).toBeInTheDocument();
    expect(screen.getByText("email.send_welcome")).toBeInTheDocument();
    expect(screen.getByText("task-001")).toBeInTheDocument();
    expect(screen.getByText("high-priority")).toBeInTheDocument();
    expect(screen.getByText("Delivered in 240ms")).toBeInTheDocument();

    expect(screen.getByText("report.generate_pdf")).toBeInTheDocument();
    expect(screen.getByText("task-002")).toBeInTheDocument();
    expect(screen.getByText("reports")).toBeInTheDocument();
  });

  it("handles filtering by status and queue input", async () => {
    const user = userEvent.setup();
    const mockRefetch = vi.fn();
    (apiHooks.useTasks as any).mockReturnValue({
      data: mockTasksData,
      isLoading: false,
      refetch: mockRefetch,
    });

    render(<TasksPage />);

    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "RUNNING");

    const queueInput = screen.getByPlaceholderText(/e\.g\. default, reports/i);
    await user.type(queueInput, "reports");

    expect(apiHooks.useTasks).toHaveBeenLastCalledWith(
      expect.objectContaining({
        status: "RUNNING",
        queue: "reports",
      })
    );

    const resetBtn = screen.getByRole("button", { name: /Reset Filters/i });
    await user.click(resetBtn);

    expect(apiHooks.useTasks).toHaveBeenLastCalledWith(
      expect.objectContaining({
        status: undefined,
        queue: undefined,
      })
    );
  });
});
