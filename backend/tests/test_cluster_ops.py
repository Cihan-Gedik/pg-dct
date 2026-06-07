from app.services.cluster_ops import _pick_candidate, resolve_container


def test_resolve_container_by_name() -> None:
    cid = "lc-pg-main"
    assert resolve_container(cid, "logcollector-cihangedik-node0") == "logcollector-cihangedik-node0"


def test_resolve_container_by_host() -> None:
    cid = "lc-pg-main"
    assert resolve_container(cid, "172.18.0.2") == "logcollector-cihangedik-node0"


def test_pick_candidate_auto() -> None:
    members = [
        {"name": "node0", "role": "leader"},
        {"name": "node1", "role": "replica"},
        {"name": "node2", "role": "replica"},
    ]
    assert _pick_candidate(members, "node0", None) == "node1"


def test_pick_candidate_preferred() -> None:
    members = [
        {"name": "node0", "role": "leader"},
        {"name": "node1", "role": "replica"},
        {"name": "node2", "role": "replica"},
    ]
    assert _pick_candidate(members, "node0", "node2") == "node2"
