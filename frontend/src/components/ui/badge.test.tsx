import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "./badge";

describe("Badge component", () => {
  it("renders with default variant", () => {
    render(<Badge>Default Badge</Badge>);
    const badge = screen.getByText("Default Badge");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("bg-primary");
  });

  it("renders with success variant", () => {
    render(<Badge variant="success">Completed</Badge>);
    const badge = screen.getByText("Completed");
    expect(badge).toHaveClass("text-emerald-700");
  });

  it("renders with warning variant", () => {
    render(<Badge variant="warning">Retrying</Badge>);
    const badge = screen.getByText("Retrying");
    expect(badge).toHaveClass("text-amber-700");
  });

  it("renders with destructive variant", () => {
    render(<Badge variant="destructive">Dead</Badge>);
    const badge = screen.getByText("Dead");
    expect(badge).toHaveClass("bg-destructive");
  });

  it("renders with info variant", () => {
    render(<Badge variant="info">Running</Badge>);
    const badge = screen.getByText("Running");
    expect(badge).toHaveClass("text-blue-700");
  });
});
