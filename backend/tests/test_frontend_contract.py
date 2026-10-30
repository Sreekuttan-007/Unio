"""Keeps the backend and the frontend honest with each other.

The frontend builds against files generated from this backend (OpenAPI types and mock fixtures)
and declares one screen per navigation key. These tests fail when either side moves alone.
"""

import re
from pathlib import Path

from app.users.navigation import CATALOG
from tools.contract import FIXTURES_PATH, OPENAPI_PATH, ROOT, build_contract

REGISTRY = ROOT / "frontend" / "src" / "platform" / "workspaces" / "registry.ts"
WORKSPACE_SCREENS = ROOT / "frontend" / "src" / "features" / "workspaces"


async def test_committed_contract_files_match_the_backend():
    expected = await build_contract()
    stale = [path for path, text in expected.items() if (ROOT / path).read_text("utf-8") != text]
    assert not stale, f"Run `python -m tools.contract` (then `npm run gen:api` in frontend) to refresh: {stale}"


def test_the_contract_files_exist():
    assert (ROOT / OPENAPI_PATH).exists() and (ROOT / FIXTURES_PATH).exists()


def test_every_navigation_key_has_a_registered_frontend_screen():
    registered = set(re.findall(r"^\s*'([a-zA-Z]+\.[a-zA-Z]+)':", REGISTRY.read_text("utf-8"), re.MULTILINE))
    backend = {entry.key for entries in CATALOG.values() for entry in entries}
    assert backend - registered == set(), "navigation keys with no screen"
    assert registered - backend == set(), "frontend screens the backend never sends"


def test_each_workspace_module_defines_exactly_its_own_screens():
    modules = {"student", "faculty", "department", "facilities", "procurement", "technician", "system"}
    assert set(CATALOG) == modules
    for workspace, entries in CATALOG.items():
        source = (WORKSPACE_SCREENS / workspace / "index.tsx").read_text("utf-8")
        defined = set(re.findall(r"^\s*'([a-zA-Z]+\.[a-zA-Z]+)':", source, re.MULTILINE))
        assert defined == {entry.key for entry in entries}, f"{workspace} workspace screens differ from the backend catalog"


def test_a_screen_is_never_defined_in_another_roles_workspace():
    for workspace in CATALOG:
        source = Path(WORKSPACE_SCREENS / workspace / "index.tsx").read_text("utf-8")
        for other, entries in CATALOG.items():
            if other == workspace:
                continue
            leaked = [entry.key for entry in entries if f"'{entry.key}'" in source]
            assert not leaked, f"{workspace} workspace contains {leaked}"
