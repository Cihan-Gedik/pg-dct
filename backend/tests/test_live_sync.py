from app.services.live_sync import parse_patroni_history


def test_parse_patroni_history_counts_switchovers() -> None:
    history = [
        [1, 100, "reason", "2026-01-01T00:00:00+00:00", "node-a"],
        [2, 200, "reason", "2026-01-01T01:00:00+00:00", "node-b"],
        [3, 300, "reason", "2026-01-01T02:00:00+00:00", "node-a"],
    ]
    changes, times = parse_patroni_history(history)
    assert changes == 2
    assert times == {"node-a": 2, "node-b": 1}
