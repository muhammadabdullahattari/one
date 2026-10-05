import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "./page";
import { apiClient } from "@/lib/api-client";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    post: vi.fn(),
  },
}));

describe("LoginPage component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders login form with username and password fields", () => {
    render(<LoginPage />);

    expect(screen.getByText("Task Engine Console")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/admin or user@domain.com/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/••••••••••••/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sign In/i })).toBeInTheDocument();
  });

  it("submits valid credentials and redirects to /dashboard", async () => {
    const user = userEvent.setup();
    (apiClient.post as any).mockResolvedValueOnce({
      token_type: "bearer",
      expires_in: 900,
      user_id: "usr-1",
      role: "operator",
      tenant_id: "default",
    });

    render(<LoginPage />);

    const usernameInput = screen.getByPlaceholderText(/admin or user@domain.com/i);
    const passwordInput = screen.getByPlaceholderText(/••••••••••••/i);
    const submitBtn = screen.getByRole("button", { name: /Sign In/i });

    await user.type(usernameInput, "operator_jane");
    await user.type(passwordInput, "SecurePass123!");
    await user.click(submitBtn);

    expect(apiClient.post).toHaveBeenCalledWith("/auth/login", {
      username: "operator_jane",
      password: "SecurePass123!",
    });

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("displays error message on authentication failure", async () => {
    const user = userEvent.setup();
    (apiClient.post as any).mockRejectedValueOnce(new Error("Invalid credentials provided."));

    render(<LoginPage />);

    const usernameInput = screen.getByPlaceholderText(/admin or user@domain.com/i);
    const passwordInput = screen.getByPlaceholderText(/••••••••••••/i);
    const submitBtn = screen.getByRole("button", { name: /Sign In/i });

    await user.type(usernameInput, "wrong_user");
    await user.type(passwordInput, "wrong_pass");
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials provided.")).toBeInTheDocument();
    });
    expect(mockPush).not.toHaveBeenCalled();
  });
});
