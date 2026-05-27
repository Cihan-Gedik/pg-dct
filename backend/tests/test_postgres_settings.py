from app.services.postgres_settings import format_setting_value, parse_settings_tsv


def test_format_8kb_unit() -> None:
    assert format_setting_value("16384", "8kB") == "128.0 MiB"


def test_format_kb_unit() -> None:
    assert format_setting_value("4096", "kB") == "4.0 MiB"


def test_format_mb_unit() -> None:
    assert format_setting_value("1024", "MB") == "1.0 GiB"


def test_parse_settings_tsv() -> None:
    raw = "shared_buffers|16384|8kB\neffective_cache_size|524288|8kB\n"
    parsed = parse_settings_tsv(raw)
    assert parsed["shared_buffers"] == ("16384", "8kB")
