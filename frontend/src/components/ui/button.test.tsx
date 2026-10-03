import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./button";

describe("Button component", () => {
  it("renders with default props and text", () => {
    render(<Button>Click me</Button>);
    const button = screen.getByRole("button", { name: /click me/i });
    expect(button).toBeInTheDocument();
    expect(button).toHaveClass("bg-primary");
  });

  it("renders with destructive variant", () => {
    render(<Button variant="destructive">Delete</Button>);
    const button = screen.getByRole("button", { name: /delete/i });
    expect(button).toHaveClass("bg-destructive");
  });

  it("renders with outline variant and sm size", () => {
    render(<Button variant="outline" size="sm">Small Outline</Button>);
    const button = screen.getByRole("button", { name: /small outline/i });
    expect(button).toHaveClass("border", "h-8");
  });

  it("handles onClick events", async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    render(<Button onClick={handleClick}>Submit</Button>);
    const button = screen.getByRole("button", { name: /submit/i });
    await user.click(button);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("is disabled when disabled prop is set", async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();
    render(<Button disabled onClick={handleClick}>Disabled Button</Button>);
    const button = screen.getByRole("button", { name: /disabled button/i });
    expect(button).toBeDisabled();
    await user.click(button);
    expect(handleClick).not.toHaveBeenCalled();
  });
});
