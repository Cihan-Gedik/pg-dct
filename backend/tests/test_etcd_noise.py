from app.services.docker_logs import LogEntry, suppress_etcd_peer_noise


def test_suppress_etcd_peer_noise() -> None:
    entries = [
        LogEntry(
            ts="t",
            node="172.18.0.4",
            member_name="n2",
            source="etcd",
            level="critical",
            message='error":"dial tcp 172.18.0.2:2380: connect: connection refused"',
        ),
        LogEntry(
            ts="t",
            node="172.18.0.4",
            member_name="n2",
            source="patroni",
            level="info",
            message="ok",
        ),
    ]
    out = suppress_etcd_peer_noise(entries, {"172.18.0.2"})
    assert len(out) == 1
    assert out[0].source == "patroni"
