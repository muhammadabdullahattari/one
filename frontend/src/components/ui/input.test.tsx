import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Input } from "./input";

describe("Input component", () => {
  it("renders with placeholder and value", () => {
    render(<Input placeholder="Enter task name" defaultValue="billing.sync" />);
    const input = screen.getByPlaceholderText("Enter task name") as HTMLInputElement;
    expect(input).toBeInTheDocument();
    expect(input.value).toBe("billing.sync");
  });

  it("handles user typing and change events", async () => {
    const handleChange = vi.fn();
    const user = userEvent.setup();
    render(<Input placeholder="Type here" onChange={handleChange} />);
    const input = screen.getByPlaceholderText("Type here");

    await user.type(input, "my-queue");
    expect(handleChange).toHaveBeenCalled();
    expect(input).toHaveValue("my-queue");
  });

  it("respects disabled attribute", async () => {
    render(<Input disabled placeholder="Disabled field" />);
    const input = screen.getByPlaceholderText("Disabled field");
    expect(input).toBeDisabled();
  });
});
