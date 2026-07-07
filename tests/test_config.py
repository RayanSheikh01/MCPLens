from config import load_config


def test_load_config_reads_upstream():
    cfg = load_config("config.yaml")
    assert cfg["servers"]["mock"]["upstream"] == "http://localhost:9000/mcp"


def test_load_config_custom_path(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(
        "servers:\n"
        "  demo:\n"
        "    upstream: \"http://x/mcp\"\n"
        "    auth: \"Bearer k\"\n"
        "storage:\n"
        "  db_path: \"./x.db\"\n"
    )
    cfg = load_config(str(p))
    assert cfg["servers"]["demo"]["auth"] == "Bearer k"
    assert cfg["storage"]["db_path"] == "./x.db"
