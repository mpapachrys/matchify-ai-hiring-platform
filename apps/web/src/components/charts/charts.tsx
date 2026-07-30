"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { StageCount, TimePoint } from "@/types/api";

/**
 * One palette, applied consistently: violet for volume, cyan for rate, and a
 * single ordered ramp for the funnel so stage progression reads left to right.
 */
const VIOLET = "#8b5cf6";
const CYAN = "#22d3ee";
const AXIS = "#7c6f99";
const GRID = "#2f2050";

const FUNNEL_RAMP = ["#5b21b6", "#6d28d9", "#7c3aed", "#8b5cf6", "#22d3ee"];

const tooltipStyle = {
  backgroundColor: "#1d1231",
  border: "1px solid #3f2c69",
  borderRadius: "10px",
  fontSize: "12px",
  color: "#f4f1fb",
} as const;

function shortDate(value: string) {
  const [, month, day] = value.split("-");
  return `${day}/${month}`;
}

export function ApplicationsOverTime({ data }: { data: TimePoint[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[#a78bfa]">Applications Over Time</CardTitle>
        <CardDescription>Daily application activity, last 30 days</CardDescription>
      </CardHeader>
      <div className="h-56 px-2 pb-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 12, left: -18, bottom: 0 }}>
            <defs>
              <linearGradient id="volumeFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={VIOLET} stopOpacity={0.5} />
                <stop offset="100%" stopColor={VIOLET} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={shortDate}
              tick={{ fill: AXIS, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: AXIS, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={34}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              labelFormatter={(v) => `Date: ${v}`}
              formatter={(v: number) => [v, "Applications"]}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke={VIOLET}
              strokeWidth={2}
              fill="url(#volumeFill)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

export function SuccessRateTrend({ data }: { data: { date: string; value: number }[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-warning">Success Rate Trend</CardTitle>
        <CardDescription>Running share of applications that were shortlisted</CardDescription>
      </CardHeader>
      <div className="h-56 px-2 pb-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 12, left: -18, bottom: 0 }}>
            <defs>
              <linearGradient id="rateFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={CYAN} stopOpacity={0.4} />
                <stop offset="100%" stopColor={CYAN} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={shortDate}
              tick={{ fill: AXIS, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
            />
            <YAxis
              domain={[0, 100]}
              tickFormatter={(v) => `${v}%`}
              tick={{ fill: AXIS, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={42}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(v: number) => [`${v}%`, "Success rate"]}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke={CYAN}
              strokeWidth={2}
              fill="url(#rateFill)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

export function HiringFunnel({ data }: { data: StageCount[] }) {
  const rows = data.map((d) => ({ ...d, label: d.stage.replace(/^\w/, (c) => c.toUpperCase()) }));
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-[#a78bfa]">Hiring Funnel</CardTitle>
        <CardDescription>Where every applicant currently sits</CardDescription>
      </CardHeader>
      <div className="h-56 px-2 pb-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 4, right: 12, left: -18, bottom: 0 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: AXIS, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: AXIS, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={34}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              cursor={{ fill: "rgba(139,92,246,0.08)" }}
              formatter={(v: number) => [v, "Candidates"]}
            />
            <Bar dataKey="count" radius={[6, 6, 0, 0]}>
              {rows.map((_, index) => (
                <Cell key={index} fill={FUNNEL_RAMP[index % FUNNEL_RAMP.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
