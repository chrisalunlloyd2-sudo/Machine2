"""DAG backup (scrubbed render -> private repo) tests."""
import json
import os
import subprocess
import tempfile

from bdi_fsm.world_model import WorldModel
from bdi_fsm.dag_backup import backup, render_world


def test_render_world_scrubs_pii():
    w = WorldModel()
    w.observe("node", "n", {"owner": "chrisalunlloyd2@gmail.com", "port": "80"})
    r = render_world(w)
    node = r["entities"][w.entity("node", "n").entity_id]["nodes"]["owner"]
    assert "chrisalunlloyd2@gmail.com" not in node["value"]


def test_backup_writes_and_commits_locally():
    d = tempfile.mkdtemp()
    repo = d + "/repo"
    os.makedirs(repo)
    subprocess.run(["git", "init", "-q", repo], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.email", "a@b.c"], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.name", "t"], check=True)

    w = WorldModel()
    w.observe("server", "localhost:8765", {"health": "up"})
    r = backup(w, repo, push=False)
    assert r["entities"] == 1
    assert os.path.exists(os.path.join(repo, "dags"))
    assert os.path.exists(os.path.join(repo, "index.json"))
    # committed
    log = subprocess.run(["git", "-C", repo, "log", "--oneline"],
                         capture_output=True, text=True)
    assert log.stdout.strip() != ""
