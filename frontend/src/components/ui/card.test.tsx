import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "./card";

describe("Card component", () => {
  it("renders card with title, description, content and footer", () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>System Overview</CardTitle>
          <CardDescription>Live health telemetry</CardDescription>
        </CardHeader>
        <CardContent>
          <p>Operational stats: All nodes green.</p>
        </CardContent>
        <CardFooter>
          <span>Last updated just now</span>
        </CardFooter>
      </Card>
    );

    expect(screen.getByText("System Overview")).toBeInTheDocument();
    expect(screen.getByText("Live health telemetry")).toBeInTheDocument();
    expect(screen.getByText("Operational stats: All nodes green.")).toBeInTheDocument();
    expect(screen.getByText("Last updated just now")).toBeInTheDocument();
  });
});
