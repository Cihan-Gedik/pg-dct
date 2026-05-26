import type { EtcdMember } from "../api";

type Props = {
  members: EtcdMember[];
  leaderName: string | null | undefined;
};

function titleCase(value: string): string {
  return value.replace(/\b\w/g, (ch) => ch.toUpperCase());
}

export function EtcdMemberTable({ members, leaderName }: Props) {
  if (!members.length) {
    return (
      <div className="card member-table-wrap">
        <h3 className="section-title">Etcd Members</h3>
        <p className="muted">Etcd member list unavailable (is Etcd running on the lab containers?).</p>
      </div>
    );
  }

  return (
    <div className="card member-table-wrap">
      <h3 className="section-title">Etcd Members</h3>
      <table>
        <thead>
          <tr>
            <th>Member</th>
            <th>Host</th>
            <th>Role</th>
            <th>State</th>
            <th>Member ID</th>
            <th>Client URL</th>
            <th>Peer URL</th>
            <th>Container</th>
          </tr>
        </thead>
        <tbody>
          {members.map((m) => (
            <tr key={m.member_id} className={m.name === leaderName || m.role === "leader" ? "row-leader" : ""}>
              <td>
                <strong>{m.name}</strong>
                {m.role === "leader" && (
                  <span className="badge leader" style={{ marginLeft: 6 }}>
                    Raft Leader
                  </span>
                )}
              </td>
              <td>{m.host || "—"}</td>
              <td>
                <span className={`badge ${m.role === "leader" ? "leader" : "replica"}`}>
                  {titleCase(m.role)}
                </span>
              </td>
              <td>
                <span
                  className={`badge ${
                    m.state === "started" ? "leader" : m.state === "down" ? "critical" : "warning"
                  }`}
                >
                  {titleCase(m.state)}
                </span>
              </td>
              <td className="mono-sm">{m.member_id}</td>
              <td className="mono-sm">{m.client_url || "—"}</td>
              <td className="mono-sm">{m.peer_url || "—"}</td>
              <td>
                {m.container ? (
                  <span className={m.container_running === false ? "text-warn" : "pill"}>
                    {m.container}
                    {m.container_running === false && " (Stopped)"}
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
