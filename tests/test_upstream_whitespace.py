"""Keep upstream EOF whitespace compatible without weakening other checks."""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = 'presentation-studio/engines/ppt-master/scripts/tests/test_preview_browser.py'


class UpstreamWhitespaceTests(unittest.TestCase):
    def test_exception_is_limited_to_known_upstream_file_and_blank_eof(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def git(*args):
                return subprocess.run(['git', '-C', str(root), *args],
                                      capture_output=True, check=False)
            self.assertEqual(git('init').returncode, 0)
            (root / '.gitattributes').write_bytes((ROOT / '.gitattributes').read_bytes())
            cases = [(UPSTREAM, b'pass\n\n', 0),
                     (UPSTREAM, b'pass \n', 2),
                     ('other.py', b'pass\n\n', 2),
                     ('presentation-studio/engines/ppt-master/scripts/tests/other.py', b'pass\n\n', 2)]
            for name, content, expected in cases:
                with self.subTest(name=name, content=content):
                    target = root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                    self.assertEqual(git('add', '--', name).returncode, 0)
                    result = git('diff', '--cached', '--check', '--', name)
                    self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                    self.assertEqual(git('show', ':' + name).stdout, content)


if __name__ == '__main__':
    unittest.main()
