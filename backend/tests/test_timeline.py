from datetime import UTC, datetime, timedelta

from app.services.timeline import build_member_timeline


def test_same_node_leader_then_replica_segments() -> None:
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    t1 = datetime(2026, 1, 7, 12, 0, tzinfo=UTC)
    t2 = datetime(2026, 1, 14, 12, 0, tzinfo=UTC)
    history = [
        [1, 0, "bootstrap", t0.isoformat(), "node-a"],
        [2, 0, "switchover", t1.isoformat(), "node-b"],
        [3, 0, "switchover", t2.isoformat(), "node-a"],
    ]
    range_start = t0 - timedelta(hours=1)
    range_end = t2 + timedelta(hours=1)
    members, switches = build_member_timeline(history, ["node-a", "node-b"], range_start, range_end, "node-a")
    node_a = next(m for m in members if m["member"] == "node-a")
    roles = [s["role"] for s in node_a["segments"]]
    assert "leader" in roles
    assert "replica" in roles
    assert len(roles) >= 2
    assert len(switches) >= 2
