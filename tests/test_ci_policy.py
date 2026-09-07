"""Guard the explicit CI boundary; repository protection still requires owner review."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CiPolicyTests(unittest.TestCase):
    def test_workflows_are_unprivileged(self):
        workflows = list((ROOT / '.github/workflows').glob('*.yml'))
        self.assertEqual(len(workflows), 1, 'Review the CI trust boundary before adding a workflow.')
        text = workflows[0].read_text()
        for forbidden in ['pull_request_target', 'workflow_run', 'secrets.', 'secrets[', 'secrets: inherit',
                          'self-hosted', 'id-token:', 'contents: write', 'pull-requests: write',
                          'environment:', 'scripts/sign.py', 'scripts/package_release.py', 'gh release',
                          'actions/download-artifact', 'actions/cache']:
            self.assertNotIn(forbidden, text)
        self.assertIn('  pull_request:', text)
        self.assertEqual(text.count('permissions:'), 1)
        self.assertRegex(text, r'permissions:\n  contents: read\n\n')
        uses = re.findall(r'uses: (\S+)', text)
        self.assertTrue(uses)
        for action in uses:
            self.assertRegex(action, r'^actions/[a-z-]+@[a-f0-9]{40}$')
        self.assertEqual(text.count('persist-credentials: false'), text.count('uses: actions/checkout@'))
        self.assertNotRegex(text, r'run:.*\$\{\{')


if __name__ == '__main__':
    unittest.main()
