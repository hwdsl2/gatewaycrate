"""Exercise existing URL/shared/YAML consumers with resolved synthetic inputs."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import quote

import yaml

ROOT = Path(__file__).resolve().parents[3]
SOURCE = (ROOT / "run.sh").read_text()


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.env = {"PATH": os.environ["PATH"], "KUBERNETES_SERVICE_HOST": "fixture",
                    "TEST_PYTHON": sys.executable}

    def run_shell(self, source, extra="", values=None):
        source = re.sub(r'^export PATH=.*$', '', source, flags=re.M)
        source = source.replace('/litellm.env', str(self.base / 'litellm.env'))
        source = source.replace('/etc/litellm', str(self.base))
        source = source.replace('/var/lib/ollama-shared', str(self.base / 'ollama-shared'))
        source = source.replace('/var/lib/mcp-shared', str(self.base / 'mcp-shared'))
        source = source.replace('/proc/mounts', str(self.base / 'mounts'))
        # Route existing embedded Python programs through the isolated test env.
        source = 'python3() { "$TEST_PYTHON" "$@"; }\n' + source + extra
        return subprocess.run(['bash', '-c', source], env={**self.env, **(values or {})},
                              capture_output=True, timeout=10)

    def test_database_url_overrides_legacy_password_file_without_a_conflict(self):
        prefix = SOURCE.split('# Ensure data directory exists', 1)[0]
        password = self.base / 'postgres password'
        password.write_bytes(b'  "old db p@ss" \r\n')
        values = {'LITELLM_POSTGRES_PASSWORD_FILE': str(password)}
        result = self.run_shell(prefix, '\nprintf "%s" "$LITELLM_DATABASE_URL"', values)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.decode(), 'postgresql://litellm:' + quote('old db p@ss', safe='') + '@db:5432/litellm')
        url = self.base / 'database url'
        expected = b'postgresql://user:p%40ss@host/db?application_name="literal"&x= '
        url.write_bytes(expected + b'\r\n')
        values.update(LITELLM_DATABASE_URL_FILE=str(url),
                      LITELLM_POSTGRES_PASSWORD_FILE=str(self.base / 'missing-password'))
        result = self.run_shell(prefix, '\nprintf "%s" "$LITELLM_DATABASE_URL"', values)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, expected)
        values['LITELLM_DATABASE_URL'] = ''
        self.assertNotEqual(self.run_shell(prefix, values=values).returncode, 0)

    def test_explicit_files_win_over_shared_fallbacks(self):
        prefix = SOURCE.split('# Apply defaults', 1)[0]
        shared = SOURCE.split('if [ -z "$LITELLM_OLLAMA_API_KEY" ]', 1)[1].split(
            '# Export provider API keys', 1)[0]
        shared = 'if [ -z "$LITELLM_OLLAMA_API_KEY" ]' + shared
        mounts = []
        values = {}
        for service in ('ollama', 'mcp'):
            folder = self.base / (service + '-shared')
            folder.mkdir()
            (folder / '.api_key').write_text('synthetic-shared-' + service)
            mounts.append('fixture ' + str(folder) + ' fixture rw 0 0\n')
            external = self.base / (service + ' external')
            external.write_text('synthetic-file-' + service + '\n')
            values['LITELLM_' + service.upper() + '_API_KEY_FILE'] = str(external)
        (self.base / 'mounts').write_text(''.join(mounts))
        output = '\nprintf "%s\\n%s" "$LITELLM_OLLAMA_API_KEY" "$LITELLM_MCP_API_KEY"'
        self.assertEqual(self.run_shell(prefix + shared, output).stdout,
                         b'synthetic-shared-ollama\nsynthetic-shared-mcp')
        self.assertEqual(self.run_shell(prefix + shared, output, values).stdout,
                         b'synthetic-file-ollama\nsynthetic-file-mcp')

    def test_yaml_consumers_preserve_data_and_saved_model_policy(self):
        prefix = SOURCE.split('# Apply defaults', 1)[0]
        helpers = 'add_model_to_config() {' + SOURCE.split('add_model_to_config() {', 1)[1].split(
            '# Create config.yaml', 1)[0]
        key = self.base / 'provider key'
        key.write_bytes(b'synthetic-provider._~+/==\r\n')
        cfg = self.base / 'config.yaml'
        cfg.write_text('model_list: []\n')
        values = {'LITELLM_OPENAI_API_KEY_FILE': str(key)}
        result = self.run_shell(prefix + helpers,
            '\nadd_model_to_config "quoted\\\"alias" openai/test "$LITELLM_OPENAI_API_KEY" "https://host/path?x=\\\"q\\\""', values)
        self.assertEqual(result.returncode, 0, result.stderr)
        model = yaml.safe_load(cfg.read_text())['model_list'][0]
        self.assertEqual(model['model_name'], 'quoted"alias')
        self.assertEqual(model['litellm_params']['api_key'], 'synthetic-provider._~+/==')
        before = cfg.read_bytes()
        result = self.run_shell(helpers,
            '\nensure_model_in_config "quoted\\\"alias" openai/new synthetic-new "" false false')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(cfg.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
