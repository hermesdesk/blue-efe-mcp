import json
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from configure import generate


class ConfigTests(unittest.TestCase):
    def test_non_bmp_launch_path_is_valid_toml(self):
        scratch=Path(__file__).resolve().parents[1]/'work';scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            root=Path(temp)/'package-📦';root.mkdir()
            (root/'launch.py').write_text('# fixture')
            out=root/'config'
            generate(Path(sys.executable),out,root)
            parsed=tomllib.loads((out/'codex.toml').read_text(encoding='utf-8'))
            self.assertEqual(parsed['mcp_servers']['blue-efe']['args'],[str(root/'launch.py')])

    def test_generated_clients_share_absolute_entrypoint_and_preserve_existing(self):
        root=Path(__file__).resolve().parents[1]
        scratch=root/'work';scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            out=Path(temp)/'đường dẫn có dấu'
            out.mkdir()
            sentinel=out/'unrelated.json';sentinel.write_text('keep')
            generate(Path(sys.executable),out,root)
            codex=tomllib.loads((out/'codex.toml').read_text(encoding='utf-8'))['mcp_servers']['blue-efe']
            desktop=json.loads((out/'claude-desktop.json').read_text(encoding='utf-8'))['mcpServers']['blue-efe']
            code=json.loads((out/'claude-code.json').read_text(encoding='utf-8'))['mcpServers']['blue-efe']
            self.assertEqual(codex['command'],desktop['command'])
            self.assertEqual(codex['args'],code['args'])
            self.assertEqual(desktop['args'],[str((root/'launch.py').resolve())])
            self.assertTrue(Path(codex['command']).is_absolute())
            self.assertEqual(sentinel.read_text(),'keep')
            before=(out/'codex.toml').read_bytes()
            generate(Path(sys.executable),out,root)
            self.assertEqual((out/'codex.toml').read_bytes(),before)

if __name__=='__main__':unittest.main()
