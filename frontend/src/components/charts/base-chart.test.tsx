import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { BaseChart } from "./base-chart";
import * as echarts from "echarts/core";

const mockInstance = {
  setOption: vi.fn(),
  showLoading: vi.fn(),
  hideLoading: vi.fn(),
  resize: vi.fn(),
  dispose: vi.fn(),
};

vi.mock("echarts/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("echarts/core")>();
  return {
    ...actual,
    init: vi.fn(() => mockInstance),
  };
});

describe("BaseChart component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const sampleOptions = {
    xAxis: { type: "category" as const, data: ["Mon", "Tue", "Wed"] },
    yAxis: { type: "value" as const },
    series: [{ data: [120, 200, 150], type: "line" as const }],
  };

  it("initializes echarts on mount and sets options", () => {
    render(<BaseChart options={sampleOptions} height="300px" width="100%" />);

    expect(echarts.init).toHaveBeenCalledTimes(1);
    expect(mockInstance.setOption).toHaveBeenCalledWith(sampleOptions, { notMerge: false });
  });

  it("handles loading state transitions", () => {
    const { rerender } = render(
      <BaseChart options={sampleOptions} loading={true} />
    );
    expect(mockInstance.showLoading).toHaveBeenCalled();

    rerender(<BaseChart options={sampleOptions} loading={false} />);
    expect(mockInstance.hideLoading).toHaveBeenCalled();
  });

  it("cleans up and disposes chart instance on unmount", () => {
    const { unmount } = render(<BaseChart options={sampleOptions} />);
    unmount();
    expect(mockInstance.dispose).toHaveBeenCalledTimes(1);
  });
});
