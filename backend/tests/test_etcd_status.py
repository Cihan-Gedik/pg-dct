import json

from app.services.etcd_status import (
    build_etcd_members,
    parse_etcd_endpoint_status,
    parse_etcd_member_list,
)

MEMBER_LIST = {
    "header": {"cluster_id": 16747017918056436306, "raft_term": 4},
    "members": [
        {
            "ID": 1276515949825239588,
            "name": "lc-pg-main21253-1",
            "peerURLs": ["http://172.18.0.3:2380"],
            "clientURLs": ["http://172.18.0.3:2379"],
        },
        {
            "ID": 7251892844326820777,
            "name": "lc-pg-main-0",
            "peerURLs": ["http://172.18.0.2:2380"],
            "clientURLs": ["http://172.18.0.2:2379"],
        },
    ],
}

ENDPOINT_STATUS = [
    {
        "Endpoint": "http://172.18.0.3:2379",
        "Status": {
            "header": {"member_id": 1276515949825239588},
            "leader": 1276515949825239588,
        },
    },
    {
        "Endpoint": "http://172.18.0.2:2379",
        "Status": {
            "header": {"member_id": 7251892844326820777},
            "leader": 1276515949825239588,
        },
    },
]


def test_parse_etcd_member_list() -> None:
    rows = parse_etcd_member_list(MEMBER_LIST)
    assert len(rows) == 2
    assert rows[0]["name"] == "lc-pg-main21253-1"
    assert rows[0]["host"] == "172.18.0.3"


def test_parse_etcd_endpoint_status_leader() -> None:
    member_by_id = {r["member_id"]: r for r in parse_etcd_member_list(MEMBER_LIST)}
    leader_name, healthy, health = parse_etcd_endpoint_status(ENDPOINT_STATUS, member_by_id)
    assert leader_name == "lc-pg-main21253-1"
    assert healthy == 2
    assert len(health) == 2


def test_build_etcd_members_roles() -> None:
    rows = parse_etcd_member_list(MEMBER_LIST)
    member_by_id = {r["member_id"]: r for r in rows}
    leader_id = f"{1276515949825239588:x}"
    health = {r["member_id"]: "up" for r in rows}
    docker_hosts = {"172.18.0.3": "node1", "172.18.0.2": "node0"}
    members = build_etcd_members(rows, leader_id, health, docker_hosts, {"node1": True, "node0": True})
    leader = next(m for m in members if m["role"] == "leader")
    assert leader["name"] == "lc-pg-main21253-1"
