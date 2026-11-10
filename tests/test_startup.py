import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


LAUNCHER = Path(__file__).resolve().parents[1] / "deploy" / "start.sh"


class StartupTests(unittest.TestCase):
    def run_launcher(self, *, fail_install=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        log = root / "processes.jsonl"
        runner = root / "python"
        runner.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "with open(os.environ['ZEBRAMOTIF_TEST_LOG'], 'a') as handle:\n"
            "    handle.write(json.dumps({\n"
            "        'args': sys.argv[1:],\n"
            "        'has_url': 'ZEBRAMOTIF_ZENODO_URL' in os.environ,\n"
            "        'has_url_file': 'ZEBRAMOTIF_ZENODO_URL_FILE' in os.environ,\n"
            "        'data_dir': os.environ['ZEBRAMOTIF_DATA_DIR'],\n"
            "    }) + '\\n')\n"
            "if sys.argv[2] == 'zebramotif.dataset':\n"
            "    sys.exit(int(os.environ['ZEBRAMOTIF_TEST_INSTALL_EXIT']))\n"
        )
        runner.chmod(0o700)
        environment = {
            **os.environ,
            "ZEBRAMOTIF_PYTHON": str(runner),
            "ZEBRAMOTIF_DATA_DIR": str(root / "persistent-data"),
            "ZEBRAMOTIF_ZENODO_URL": "test-secret-url",
            "ZEBRAMOTIF_ZENODO_URL_FILE": "/run/secrets/test-share-url",
            "ZEBRAMOTIF_HOST": "127.0.0.1",
            "ZEBRAMOTIF_PORT": "8099",
            "ZEBRAMOTIF_TEST_LOG": str(log),
            "ZEBRAMOTIF_TEST_INSTALL_EXIT": "1" if fail_install else "0",
        }
        result = subprocess.run(
            ["bash", str(LAUNCHER)],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        records = [json.loads(line) for line in log.read_text().splitlines()]
        return result, records

    def test_installer_gets_secret_and_workers_get_only_the_shared_cache(self):
        result, records = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(records), 2)
        installation, workers = records
        self.assertEqual(installation["args"], ["-m", "zebramotif.dataset"])
        self.assertTrue(installation["has_url"])
        self.assertTrue(installation["has_url_file"])
        self.assertEqual(
            workers["args"][:3], ["-m", "gunicorn", "zebramotif.app:server"]
        )
        self.assertIn("127.0.0.1:8099", workers["args"])
        self.assertFalse(workers["has_url"])
        self.assertFalse(workers["has_url_file"])
        self.assertEqual(workers["data_dir"], installation["data_dir"])
        self.assertNotIn("test-secret-url", result.stdout + result.stderr)

    def test_installation_failure_prevents_workers_from_starting(self):
        result, records = self.run_launcher(fail_install=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["args"], ["-m", "zebramotif.dataset"])


if __name__ == "__main__":
    unittest.main()
