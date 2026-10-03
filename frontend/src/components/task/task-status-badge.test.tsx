import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TaskStatusBadge } from "./task-status-badge";
import { TaskStatus } from "@/types/api";

describe("TaskStatusBadge component", () => {
  const allStatuses: TaskStatus[] = [
    "SUCCEEDED",
    "RUNNING",
    "RETRY_WAIT",
    "SCHEDULED",
    "FAILED",
    "TIMED_OUT",
    "DEAD",
    "CANCELLED",
    "QUEUED",
    "PENDING",
  ];

  allStatuses.forEach((status) => {
    it(`renders correctly for status: ${status}`, () => {
      render(
        <TaskStatusBadge
          task={{
            status,
            task_type: "email.send",
            max_attempts: 3,
            attempt_count: 1,
            queue: "default",
          }}
          showReason={true}
        />
      );
      expect(screen.getByText(status)).toBeInTheDocument();
    });
  });

  it("displays custom status_reason when provided", () => {
    render(
      <TaskStatusBadge
        task={{
          status: "FAILED",
          status_reason: "Connection to SMTP server timed out after 3000ms",
        }}
        showReason={true}
      />
    );

    expect(screen.getByText("FAILED")).toBeInTheDocument();
    expect(
      screen.getByText("Connection to SMTP server timed out after 3000ms")
    ).toBeInTheDocument();
  });

  it("hides status explanation when showReason is false", () => {
    render(
      <TaskStatusBadge
        task={{
          status: "SUCCEEDED",
          status_reason: "Completed without errors",
        }}
        showReason={false}
      />
    );

    expect(screen.getByText("SUCCEEDED")).toBeInTheDocument();
    expect(screen.queryByText("Completed without errors")).not.toBeInTheDocument();
  });

  it("renders dead-letter queue explanation for DEAD status", () => {
    render(
      <TaskStatusBadge
        task={{
          status: "DEAD",
          max_attempts: 5,
        }}
        showReason={true}
      />
    );

    expect(screen.getByText("DEAD")).toBeInTheDocument();
    expect(
      screen.getByText("All 5 retry attempts exhausted; moved to Dead Letter Queue")
    ).toBeInTheDocument();
  });
});
