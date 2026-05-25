from app.services.dashboard_issues import dedupe_issues, normalize_message


def test_dedupe_groups_repeated_etcd_errors() -> None:
    msg = 'error":"dial tcp 172.18.0.2:2380: connect: connection refused"'
    issues = [
        {
            "cluster_id": "c1",
            "cluster_name": "c1",
            "level": "critical",
            "kind": "log",
            "category": "etcd",
            "member_name": "n1",
            "host": "172.18.0.4",
            "source": "etcd",
            "title": "t",
            "message": msg,
            "detail": msg,
            "ts": "2026-05-23T10:00:00+00:00",
        },
        {
            "cluster_id": "c1",
            "cluster_name": "c1",
            "level": "critical",
            "kind": "log",
            "category": "etcd",
            "member_name": "n1",
            "host": "172.18.0.4",
            "source": "etcd",
            "title": "t",
            "message": msg + " ",
            "detail": msg,
            "ts": "2026-05-23T10:01:00+00:00",
        },
    ]
    out = dedupe_issues(issues)
    assert len(out) == 1
    assert out[0]["occurrence_count"] == 2


def test_normalize_strips_timestamps() -> None:
    a = normalize_message('{"ts":"2026-05-23T10:00:00Z","msg":"fail"}')
    b = normalize_message('{"ts":"2026-05-23T11:00:00Z","msg":"fail"}')
    assert a == b
