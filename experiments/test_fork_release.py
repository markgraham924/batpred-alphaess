"""Exercise real update-card publishing without starting Predbat."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import unittest

ROOT = Path(__file__).parents[1] / "apps/predbat"


class ForkReleaseTests(unittest.TestCase):
    """Updates must stay in the fork and link to the offered release."""

    def test_default_download_source_is_fork(self):
        """Default startup, release discovery and tagged downloads share this source."""
        scope = {}
        tree = ast.parse((ROOT / "download.py").read_text())
        node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DEFAULT_PREDBAT_REPOSITORY" for t in n.targets))
        exec(compile(ast.Module(body=[node], type_ignores=[]), "download.py", "exec"), scope)
        self.assertEqual(scope["DEFAULT_PREDBAT_REPOSITORY"], "markgraham924/batpred-alphaess")

    def test_update_card_links_to_latest_fork_release(self):
        """A future update links to its new tag, while matching tags clear the alert."""
        tree = ast.parse((ROOT / "userinterface.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "UserInterface")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "expose_config")
        scope = {"DEFAULT_PREDBAT_REPOSITORY": "markgraham924/batpred-alphaess"}
        exec(compile(ast.Module(body=[method], type_ignores=[]), "userinterface.py", "exec"), scope)
        for installed, latest, expected in [("v9.0.2-alphaess.3", "v9.0.2-alphaess.3", "off"), ("v9.0.2-alphaess.3", "v9.0.2-alphaess.4", "on")]:
            item = dict(type="update", entity="update.predbat_version", installed_version=installed, friendly_name="Predbat", title="Predbat", entity_picture="")
            obj = SimpleNamespace(config_index={"version": item}, user_config_item_enabled=lambda _: True, releases={"latest": latest}, set_state_wrapper=Mock())
            scope["expose_config"](obj, "version", False, force=True)
            result = obj.set_state_wrapper.call_args.kwargs
            self.assertEqual(result["state"], expected)
            self.assertEqual(result["attributes"]["release_url"], f"https://github.com/markgraham924/batpred-alphaess/releases/tag/{latest}")
