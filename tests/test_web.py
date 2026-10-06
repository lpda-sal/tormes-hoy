"""Static checks of the web app (no browser needed)."""

import json
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"


def _js_files() -> list[Path]:
    return [p for p in WEB.rglob("*.js") if "vendor" not in p.parts]


def test_service_worker_shell_files_exist() -> None:
    source = (WEB / "sw.js").read_text(encoding="utf-8")
    block = re.search(r"const SHELL = \[(.*?)\];", source, re.S)
    assert block is not None
    files = re.findall(r'"([^"]+)"', block.group(1))
    missing = [f for f in files if f != "./" and not (WEB / f).exists()]
    assert missing == []


def test_every_translation_key_exists() -> None:
    strings = json.loads((WEB / "i18n" / "es.json").read_text("utf-8"))

    def has(key: str) -> bool:
        node: object = strings
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return False
            node = node[part]
        return isinstance(node, str)

    keys = {
        key
        for path in _js_files()
        for key in re.findall(r'\bt\("([\w.]+)"', path.read_text("utf-8"))
    }
    assert keys, "no t() calls found"
    assert sorted(k for k in keys if not has(k)) == []


def test_chartjs_is_only_used_by_the_wrapper() -> None:
    users = [
        p.name for p in _js_files() if "window.Chart" in p.read_text("utf-8")
    ]
    assert users == ["charts.js"]
