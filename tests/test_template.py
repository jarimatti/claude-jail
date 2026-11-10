"""Render every agent selection with Copier; run with mise run test."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class TemplateTests(unittest.TestCase):
    def test_agent_selections(self):
        with tempfile.TemporaryDirectory(prefix="claude-jail-test-") as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            repository = Path(__file__).resolve().parents[1]
            shutil.copy(repository / "copier.yml", source)
            shutil.copytree(repository / "template", source / "template")
            for agents in ("claude", "codex", "both"):
                with self.subTest(agents=agents):
                    destination = root / agents
                    subprocess.run([
                        "copier", "copy", "--defaults", "--quiet",
                        "--data", f"agents={agents}",
                        "--data", "extra_domains=[example.com]",
                        str(source), str(destination),
                    ], check=True)
                    container = destination / ".devcontainer"
                    config = json.loads((container / "devcontainer.json").read_text())
                    compose = (container / "docker-compose.yml").read_text()
                    domains = (container / "proxy/allowed-domains.txt").read_text()
                    installer = (container / "install.sh").read_text()
                    claude = agents in ("claude", "both")
                    codex = agents in ("codex", "both")
                    self.assertEqual("CODEX_HOME" in config["containerEnv"], codex)
                    self.assertEqual("CLAUDE_CONFIG_DIR" in config["containerEnv"], claude)
                    self.assertEqual("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC" in config["containerEnv"], claude)
                    self.assertEqual("codex-config:" in compose, codex)
                    self.assertEqual("claude-config:" in compose, claude)
                    self.assertEqual("auth.openai.com" in domains, codex)
                    self.assertEqual(".anthropic.com" in domains, claude)
                    self.assertEqual("--release latest" in installer, codex)
                    self.assertEqual("https://claude.ai/install.sh" in installer, claude)
                    self.assertIn("example.com", domains)
                    self.assertEqual(
                        config["customizations"]["vscode"]["extensions"],
                        (["anthropic.claude-code"] if claude else [])
                        + (["openai.chatgpt"] if codex else []),
                    )
                    self.assertIn("cap_drop: [ALL]", compose)
                    self.assertIn("internal: true", compose)
                    subprocess.run(["bash", "-n", str(container / "install.sh")], check=True)
                    recipes = subprocess.check_output([
                        "just", "--justfile", str(destination / "justfile"), "--list",
                    ], text=True)
                    self.assertIn("codex", recipes)
                    # Capture the actual argv passed to npx without starting a container.
                    binaries = destination / "bin"
                    binaries.mkdir()
                    npx = binaries / "npx"
                    npx.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
                    npx.chmod(0o755)
                    prompt = "Reply with OK. Do not use tools."
                    for command in (["codex", "exec", prompt], ["claude", "-p", prompt]):
                        arguments = subprocess.check_output([
                            "just", "--justfile", str(destination / "justfile"), *command,
                        ], env={**os.environ, "PATH": str(binaries) + os.pathsep + os.environ["PATH"]},
                            text=True)
                        self.assertEqual(arguments.splitlines()[-3:], command)



if __name__ == "__main__":
    unittest.main()
