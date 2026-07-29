"use client";

import { useEffect, useRef } from "react";
import {
  ColorType,
  createChart,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";
import type { Candle } from "@/types";

type Zone = {
  type?: string;
  top?: number | null;
  bottom?: number | null;
  price?: number | null;
  direction?: string | null;
};

function toUnixSec(t: number): number {
  // ms → sec if needed
  return t > 1_000_000_000_000 ? Math.floor(t / 1000) : Math.floor(t);
}

export function PriceChart({
  candles,
  zones = [],
  emptyHint = "Нет свечей — нажмите «Загрузить анализ»",
}: {
  candles: Candle[];
  zones?: Zone[];
  emptyHint?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      width: ref.current.clientWidth || 600,
      height: 420,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#a1a1aa",
      },
      grid: {
        vertLines: { color: "#27272a" },
        horzLines: { color: "#27272a" },
      },
      rightPriceScale: { borderColor: "#27272a" },
      timeScale: { borderColor: "#27272a" },
    });
    const series = chart.addCandlestickSeries({
      upColor: "#00FF88",
      downColor: "#FF4444",
      borderVisible: false,
      wickUpColor: "#00FF88",
      wickDownColor: "#FF4444",
    });
    chartRef.current = chart;
    seriesRef.current = series;

    const ro = new ResizeObserver(() => {
      if (ref.current) chart.applyOptions({ width: ref.current.clientWidth });
    });
    ro.observe(ref.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current) return;
    if (!candles.length) {
      seriesRef.current.setData([]);
      return;
    }
    const data = candles
      .map((c) => ({
        time: toUnixSec(Number(c.time)) as import("lightweight-charts").UTCTimestamp,
        open: Number(c.open),
        high: Number(c.high),
        low: Number(c.low),
        close: Number(c.close),
      }))
      .filter((c) => Number.isFinite(c.open) && Number.isFinite(c.time))
      .sort((a, b) => Number(a.time) - Number(b.time));

    // lightweight-charts requires unique ascending times
    const dedup: typeof data = [];
    for (const row of data) {
      if (dedup.length && dedup[dedup.length - 1].time === row.time) {
        dedup[dedup.length - 1] = row;
      } else {
        dedup.push(row);
      }
    }

    try {
      seriesRef.current.setData(dedup);
      chartRef.current?.timeScale().fitContent();
    } catch (err) {
      console.error("chart setData failed", err);
    }

    const lines: Array<ReturnType<ISeriesApi<"Candlestick">["createPriceLine"]>> = [];
    for (const z of zones.slice(0, 8)) {
      if (z.top != null) {
        lines.push(
          seriesRef.current.createPriceLine({
            price: z.top,
            color: z.type?.includes("bearish") ? "#FF4444" : "#00FF88",
            lineWidth: 1,
            axisLabelVisible: true,
            title: z.type || "zone",
          })
        );
      }
      if (z.bottom != null) {
        lines.push(
          seriesRef.current.createPriceLine({
            price: z.bottom,
            color: "#FFC107",
            lineWidth: 1,
            axisLabelVisible: true,
            title: "zone low",
          })
        );
      } else if (z.price != null) {
        lines.push(
          seriesRef.current.createPriceLine({
            price: z.price,
            color: "#7aa2ff",
            lineWidth: 1,
            axisLabelVisible: true,
            title: z.type || "liq",
          })
        );
      }
    }
    return () => {
      void lines;
    };
  }, [candles, zones]);

  return (
    <div className="relative w-full">
      <div ref={ref} className="w-full min-h-[420px] rounded-xl border border-line bg-panel/40" />
      {!candles.length && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <p className="text-sm text-mist bg-ink/70 px-4 py-2 rounded-md">{emptyHint}</p>
        </div>
      )}
    </div>
  );
}
