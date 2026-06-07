import type { LiveMember } from "../api";

type Props = {
  members: LiveMember[];
  leader: string | null;
  title?: string;
  dockerLab?: boolean;
  busyMember?: string | null;
  onStart?: (member: LiveMember) => void;
  onStop?: (member: LiveMember) => void;
  onSwitchover?: (member: LiveMember) => void;
};

export function MemberTable({
  members,
  leader,
  title = "Patroni members",
  dockerLab = false,
  busyMember = null,
  onStart,
  onStop,
  onSwitchover,
}: Props) {
  const showActions = dockerLab && (onStart || onStop || onSwitchover);

  return (
    <div className="card member-table-wrap">
      <h3 className="section-title">{title}</h3>
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
            {showActions && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {members.map((m) => {
            const busy = busyMember != null && (busyMember === m.name || busyMember === "__global__");
            const isLeader = m.name === leader;
            const isReplica = m.role === "replica";
            return (
              <tr key={m.name} className={isLeader ? "row-leader" : ""}>
                <td>
                  <strong>{m.name}</strong>
                  {isLeader && <span className="badge leader" style={{ marginLeft: 6 }}>primary</span>}
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
                {showActions && (
                  <td className="action-links">
                    {onStart && (
                      <button
                        type="button"
                        className="btn btn-sm"
                        disabled={busy || m.container_running !== false}
                        onClick={() => onStart(m)}
                      >
                        Start
                      </button>
                    )}
                    {onStop && (
                      <button
                        type="button"
                        className="btn btn-sm"
                        disabled={busy || m.container_running === false}
                        onClick={() => onStop(m)}
                      >
                        Stop
                      </button>
                    )}
                    {onSwitchover && isReplica && !isLeader && (
                      <button
                        type="button"
                        className="btn btn-sm primary"
                        disabled={busy}
                        onClick={() => onSwitchover(m)}
                      >
                        Switchover
                      </button>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
