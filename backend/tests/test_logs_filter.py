from app.services.docker_logs import classify_level


def test_classify_critical() -> None:
    assert classify_level("ERROR: connection failed") == "critical"
    assert classify_level("WARNING: lag high") == "warning"
    assert classify_level("started streaming") == "info"
