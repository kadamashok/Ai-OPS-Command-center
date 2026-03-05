import React, { useEffect, useState } from "react";

import { fetchDashboardSummary } from "../api/client";
import { IncidentTable } from "../components/IncidentTable";
import { KpiCard } from "../components/KpiCard";

type DashboardPayload = {
  global_business_health: {
    orders_per_minute: number;
    store_billing_per_minute: number;
    payment_success_rate: number;
    inventory_sync_latency_ms: number;
    dispatch_queue_size: number;
  };
  active_incidents: Array<{
    id: string;
    root_cause: string;
    automation: string;
    status: string;
  }>;
};

export default function App() {
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    fetchDashboardSummary().then(setData).catch(() => {
      setError("Failed to fetch dashboard data. Ensure dashboard-service is reachable.");
    });
  }, []);

  return (
    <div className="layout">
      <header className="hero">
        <h1>CAROP Command Center</h1>
        <p>Autonomous Retail Operations for Croma Enterprise Systems</p>
      </header>

      {error ? <div className="error">{error}</div> : null}

      <section className="grid">
        <KpiCard title="Orders / Min" value={data?.global_business_health.orders_per_minute ?? "--"} />
        <KpiCard title="Store Billing / Min" value={data?.global_business_health.store_billing_per_minute ?? "--"} />
        <KpiCard title="Payment Success %" value={data?.global_business_health.payment_success_rate ?? "--"} />
        <KpiCard title="Inventory Sync Latency" value={`${data?.global_business_health.inventory_sync_latency_ms ?? "--"} ms`} />
        <KpiCard title="Dispatch Queue Size" value={data?.global_business_health.dispatch_queue_size ?? "--"} />
      </section>

      <IncidentTable incidents={data?.active_incidents ?? []} />
    </div>
  );
}
