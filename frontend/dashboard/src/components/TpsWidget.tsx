type TpsMetric = {
  application: string;
  current_tps: number;
  avg_5m_tps: number;
  baseline_tps: number;
  status: "normal" | "drop" | "spike";
};

type TpsAlert = {
  application: string;
  status: "drop" | "spike";
  reason: string;
  current_tps: number;
  avg_5m_tps: number;
  baseline_tps: number;
};

type Props = {
  metrics: TpsMetric[];
  alerts: TpsAlert[];
};

export function TpsWidget({ metrics, alerts }: Props) {
  const alertMap = new Map(alerts.map((a) => [a.application, a]));

  return (
    <section className="panel">
      <h2>TPS Monitor (Rolling 5 Minutes)</h2>
      <table>
        <thead>
          <tr>
            <th>Application</th>
            <th>Current TPS</th>
            <th>5 Minute Avg TPS</th>
            <th>Baseline TPS</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((m) => {
            const alert = alertMap.get(m.application);
            const statusClass = m.status === "normal" ? "status-normal" : m.status === "drop" ? "status-drop" : "status-spike";
            return (
              <tr key={m.application}>
                <td>{m.application}</td>
                <td>{m.current_tps.toFixed(3)}</td>
                <td>{m.avg_5m_tps.toFixed(3)}</td>
                <td>{m.baseline_tps.toFixed(3)}</td>
                <td>
                  <span className={`badge ${statusClass}`}>
                    {m.status}
                    {alert ? ` (${alert.reason})` : ""}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
