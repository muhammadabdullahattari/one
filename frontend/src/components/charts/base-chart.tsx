"use client";

import React, { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import {
  LineChart,
  BarChart,
  PieChart,
} from "echarts/charts";
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";

echarts.use([
  LineChart,
  BarChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  CanvasRenderer,
]);

interface BaseChartProps {
  options: EChartsCoreOption;
  height?: string | number;
  width?: string | number;
  className?: string;
  loading?: boolean;
}

export function BaseChart({
  options,
  height = "320px",
  width = "100%",
  className,
  loading = false,
}: BaseChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = echarts.init(containerRef.current);
    chartInstanceRef.current = chart;
    chart.setOption(options, { notMerge: false });

    if (loading) {
      chart.showLoading({
        text: "Loading real-time telemetry...",
        color: "#3b82f6",
        textColor: "#64748b",
        maskColor: "rgba(255, 255, 255, 0.6)",
      });
    }

    const resizeObserver = new ResizeObserver(() => {
      chart.resize();
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.dispose();
      chartInstanceRef.current = null;
    };
  }, []); // Run on mount & unmount only

  useEffect(() => {
    if (!chartInstanceRef.current) return;
    chartInstanceRef.current.setOption(options, { notMerge: false });
  }, [options]);

  useEffect(() => {
    if (!chartInstanceRef.current) return;
    if (loading) {
      chartInstanceRef.current.showLoading({
        text: "Loading real-time telemetry...",
        color: "#3b82f6",
        textColor: "#64748b",
        maskColor: "rgba(255, 255, 255, 0.6)",
      });
    } else {
      chartInstanceRef.current.hideLoading();
    }
  }, [loading]);

  return (
    <div
      ref={containerRef}
      style={{ height, width }}
      className={`relative w-full ${className || ""}`}
    />
  );
}
