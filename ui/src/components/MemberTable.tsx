import type { LiveMember } from "../api";

type Props = {
  members: LiveMember[];
  leader: string | null;
};

export function MemberTable({ members, leader }: Props) {
  return (
    <div className="card member-table-wrap">
      <h3 className="section-title">Members</h3>
      <table>
        <thead>
          <tr>
            <th>Member</th>
            <th>Host</th>
            <th>Role</th>
            <th>State</th>
            <th>Timeline</th>
            <th>Lag</th>
            <th>Switchovers</th>
            <th>Container</th>
          </tr>
        </thead>
        <tbody>
          {members.map((m) => (
            <tr key={m.name} className={m.name === leader ? "row-leader" : ""}>
              <td>
                <strong>{m.name}</strong>
                {m.name === leader && <span className="badge leader" style={{ marginLeft: 6 }}>primary</span>}
              </td>
              <td>{m.host}</td>
              <td>
                <span
                  className={`badge ${
                    m.role === "leader" ? "leader" : m.role === "unreachable" ? "critical" : "replica"
                  }`}
                >
                  {m.role}
                </span>
              </td>
              <td>{m.state ?? "—"}</td>
              <td>{m.timeline ?? "—"}</td>
              <td>{m.lag != null ? m.lag : "—"}</td>
              <td>{m.switchover_count}</td>
              <td>
                {m.container ? (
                  <span className={m.container_running === false ? "text-warn" : "pill"}>
                    {m.container}
                    {m.container_running === false && " (stopped)"}
                    {m.container_running === true && " ✓"}
                  </span>
                ) : (
                  "—"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
