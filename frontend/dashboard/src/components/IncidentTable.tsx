import React from "react";

type Incident = {
  id: string;
  root_cause: string;
  automation: string;
  status: string;
};

export function IncidentTable({ incidents }: { incidents: Incident[] }) {
  return (
    <div className="panel">
      <h3>Active Incidents</h3>
      <table>
        <thead>
          <tr>
            <th>Incident</th>
            <th>Root Cause</th>
            <th>Automation</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {incidents.map((i) => (
            <tr key={i.id}>
              <td>{i.id}</td>
              <td>{i.root_cause}</td>
              <td>{i.automation}</td>
              <td><span className="badge">{i.status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
