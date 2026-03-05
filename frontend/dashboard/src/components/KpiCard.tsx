import React from "react";

type Props = {
  title: string;
  value: string | number;
  hint?: string;
};

export function KpiCard({ title, value, hint }: Props) {
  return (
    <div className="kpi-card">
      <div className="kpi-title">{title}</div>
      <div className="kpi-value">{value}</div>
      {hint ? <div className="kpi-hint">{hint}</div> : null}
    </div>
  );
}
