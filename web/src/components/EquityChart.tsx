import { useEffect, useRef } from "react";

export interface EquityPoint {
  ts: number;
  equity: number;
}

export default function EquityChart({
  points,
  baseline,
  height = 220,
}: {
  points: EquityPoint[];
  baseline?: number;
  height?: number;
}) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const W = canvas.clientWidth || 300;
    const H = height;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);

    const pad = 10;
    ctx.strokeStyle = "rgba(127,141,176,0.12)";
    ctx.lineWidth = 1;
    for (let i = 1; i < 4; i++) {
      const y = (H / 4) * i;
      ctx.beginPath();
      ctx.moveTo(pad, y);
      ctx.lineTo(W - pad, y);
      ctx.stroke();
    }

    const data = points.map((p) => p.equity);
    if (data.length === 0) {
      ctx.fillStyle = "rgba(127,141,176,0.7)";
      ctx.font = "12px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("No equity history yet — run a cycle or enable the autopilot", W / 2, H / 2);
      return;
    }

    let min = Math.min(...data);
    let max = Math.max(...data);
    if (baseline != null) {
      min = Math.min(min, baseline);
      max = Math.max(max, baseline);
    }
    if (max - min < 1e-9) {
      const nudge = Math.max(1, Math.abs(max) * 0.01);
      max += nudge;
      min -= nudge;
    }
    const x = (i: number) =>
      data.length === 1 ? W / 2 : pad + (i / (data.length - 1)) * (W - 2 * pad);
    const y = (v: number) => pad + (1 - (v - min) / (max - min)) * (H - 2 * pad);

    if (baseline != null) {
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = "rgba(241,196,15,0.55)";
      ctx.beginPath();
      const b = y(baseline);
      ctx.moveTo(pad, b);
      ctx.lineTo(W - pad, b);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    const grad = ctx.createLinearGradient(0, pad, 0, H - pad);
    grad.addColorStop(0, "rgba(74,163,255,0.35)");
    grad.addColorStop(1, "rgba(74,163,255,0.02)");

    ctx.beginPath();
    ctx.moveTo(x(0), y(data[0]));
    for (let i = 1; i < data.length; i++) ctx.lineTo(x(i), y(data[i]));
    ctx.strokeStyle = "#4aa3ff";
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.stroke();

    ctx.lineTo(x(data.length - 1), H - pad);
    ctx.lineTo(x(0), H - pad);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();
  }, [points, baseline, height]);

  return <canvas ref={ref} style={{ width: "100%", height }} />;
}