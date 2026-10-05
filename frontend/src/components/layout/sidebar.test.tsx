import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Sidebar } from "./sidebar";
import { apiClient } from "@/lib/api-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Mock next/navigation
const mockUsePathname = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
}));

// Mock apiClient
vi.mock("@/lib/api-client", () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn().mockResolvedValue({ username: "testuser", tenant_id: "test-tenant" }),
  },
}));

function renderSidebar() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <Sidebar />
    </QueryClientProvider>
  );
}

describe("Sidebar component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUsePathname.mockReturnValue("/dashboard");
    // Mock window.location
    delete (window as any).location;
    window.location = { href: "" } as any;
  });

  it("renders all navigation items with labels and badges", () => {
    renderSidebar();

    expect(screen.getByText("Task Engine")).toBeInTheDocument();
    expect(screen.getByText("v5.0 Engine Live")).toBeInTheDocument();

    expect(screen.getByRole("link", { name: /Dashboard/i })).toHaveAttribute("href", "/dashboard");
    expect(screen.getByRole("link", { name: /Live Console/i })).toHaveAttribute("href", "/live");
    expect(screen.getByRole("link", { name: /Task Backlog/i })).toHaveAttribute("href", "/tasks");
    expect(screen.getByRole("link", { name: /Queues/i })).toHaveAttribute("href", "/queues");
    expect(screen.getByRole("link", { name: /Worker Fleet/i })).toHaveAttribute("href", "/workers");
    expect(screen.getByRole("link", { name: /Schedules/i })).toHaveAttribute("href", "/schedules");
    expect(screen.getByRole("link", { name: /Dead Letter Queue/i })).toHaveAttribute("href", "/dlq");
    expect(screen.getByRole("link", { name: /Analytics/i })).toHaveAttribute("href", "/metrics");

    // Badges
    expect(screen.getByText("Flower")).toBeInTheDocument();
    expect(screen.getByText("Grafana")).toBeInTheDocument();
  });

  it("highlights active item based on current pathname", () => {
    mockUsePathname.mockReturnValue("/tasks");
    renderSidebar();

    const tasksLink = screen.getByRole("link", { name: /Task Backlog/i });
    expect(tasksLink.className).toContain("bg-primary text-primary-foreground");

    const dashboardLink = screen.getByRole("link", { name: /Dashboard/i });
    expect(dashboardLink.className).not.toContain("bg-primary text-primary-foreground");
  });

  it("handles logout call and redirects to /login", async () => {
    const user = userEvent.setup();
    (apiClient.post as any).mockResolvedValueOnce({ success: true });

    renderSidebar();

    const logoutButton = screen.getByRole("button", { name: /Sign Out/i });
    await user.click(logoutButton);

    expect(apiClient.post).toHaveBeenCalledWith("/auth/logout");
    await waitFor(() => {
      expect(window.location.href).toBe("/login");
    });
  });
});
