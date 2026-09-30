#!/usr/bin/env python3
"""Exercise timezone validation and failure handling without changing host time."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parent.parent / "configs/releng/airootfs/usr/local/bin/setup-live-timezone"


class TimezoneTests(unittest.TestCase):
    def run_lookup(self, value, lookup_status=0, setter_status=0):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mocks = {
                "ipiptimezone": '#!/bin/sh\nprintf "%s\\n" "$TEST_ZONE"\nexit "$LOOKUP_STATUS"\n',
                "timedatectl": '''#!/bin/sh
case "$1" in
    list-timezones) printf 'UTC\\nAsia/Shanghai\\nAmerica/Denver\\n' ;;
    set-timezone) printf '%s' "$2" > "$SETTER_LOG"; exit "$SETTER_STATUS" ;;
    *) exit 99 ;;
esac
''',
            }
            for name, content in mocks.items():
                path = root / name
                path.write_text(content)
                path.chmod(0o755)
            log = root / "setter.log"
            env = dict(os.environ, PATH=f"{root}:/usr/bin", TEST_ZONE=value,
                       LOOKUP_STATUS=str(lookup_status), SETTER_STATUS=str(setter_status),
                       SETTER_LOG=str(log))
            result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
            return result, log.read_text() if log.exists() else None

    def test_valid_timezone(self):
        result, applied = self.run_lookup("Asia/Shanghai")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(applied, "Asia/Shanghai")

    def test_invalid_results_do_not_change_timezone(self):
        for value in ("", "-", "Unknown/Zone", "../etc/passwd", "UTC\nAsia/Shanghai", " Asia/Shanghai"):
            with self.subTest(value=value):
                result, applied = self.run_lookup(value)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(applied)

    def test_network_failure_does_not_apply_partial_output(self):
        result, applied = self.run_lookup("Asia/Shanghai", lookup_status=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(applied)

    def test_setter_failure_is_retryable(self):
        result, _ = self.run_lookup("Asia/Shanghai", setter_status=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Live timezone set", result.stdout)


if __name__ == "__main__":
    unittest.main()
