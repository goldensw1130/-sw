# -*- coding: utf-8 -*-
"""릴리스 도구 품질 게이트 테스트. 외부 네트워크와 실제 API 키를 사용하지 않습니다."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import Prepare_Release as release
import ShortCompassServer as app

ROOT = Path(__file__).resolve().parent
CURRENT_VERSION = app.APP_VERSION


class ReleaseToolValidationTests(unittest.TestCase):
    def test_version_and_repository_validation(self):
        self.assertEqual(release.version_tuple('v2.40'), release.version_tuple('2.40.0'))
        self.assertGreater(release.version_tuple('2.100'), release.version_tuple('2.99'))
        for value in ('latest', '../2.40', '2.40-beta'):
            with self.assertRaises(ValueError):
                release.version_tuple(value)
        self.assertEqual(release.validate_repository('acme/project'), 'acme/project')
        for value in ('OWNER/REPOSITORY', 'owner', '../repo/name', 'owner/repo?query=1'):
            with self.assertRaises(ValueError):
                release.validate_repository(value)

    def test_secret_scan_flags_without_printing_value(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'sample.txt'
            fake = 'sk-' + ('A' * 36)
            path.write_text('not a real credential for test: ' + fake, encoding='utf-8')
            findings = release.scan_for_secrets(td, ['sample.txt'])
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]['type'], 'OpenAI-like API key')
            self.assertNotIn(fake, json.dumps(findings))

    def test_source_version_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'APP_VERSION'):
            release.validate_source_tree(ROOT, '2.41')

    def test_builds_manifest_and_exact_allowed_zip(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / 'out1'
            result = release.build_release(ROOT, CURRENT_VERSION, 'example/short-compass', output,
                                           minimum_version='2.38', notes_text='검증용 릴리스 메모')
            package = Path(result['packagePath'])
            manifest = json.loads(Path(result['manifestPath']).read_text(encoding='utf-8'))
            self.assertTrue(package.is_file())
            self.assertEqual(manifest['version'], CURRENT_VERSION)
            self.assertEqual(manifest['minimumVersion'], '2.38')
            self.assertEqual(manifest['releaseNotes'], '검증용 릴리스 메모')
            self.assertEqual(manifest['sha256'], hashlib.sha256(package.read_bytes()).hexdigest())
            self.assertTrue(manifest['downloadUrl'].endswith('/v{}/ShortCompass-v{}.zip'.format(CURRENT_VERSION, CURRENT_VERSION)))
            self.assertEqual(result['manifestUrl'], 'https://github.com/example/short-compass/releases/latest/download/update_manifest.json')
            with zipfile.ZipFile(str(package)) as archive:
                self.assertEqual(archive.namelist(), release.allowed_package_files(ROOT / 'ShortCompassServer.py'))
                self.assertIsNone(archive.testzip())
                packaged_server = archive.read('ShortCompassServer.py').decode('utf-8')
                self.assertIn("DEFAULT_UPDATE_MANIFEST_URL = \"https://github.com/example/short-compass/releases/latest/download/update_manifest.json\"", packaged_server)
            digest, names = app._validate_update_zip_bytes(package.read_bytes(), manifest['sha256'], CURRENT_VERSION)
            self.assertEqual(digest, manifest['sha256'])
            self.assertEqual(len(names), result['fileCount'])
            self.assertEqual(Path(result['sumsPath']).read_text(encoding='ascii').split()[0], result['sha256'])

    def test_build_is_reproducible(self):
        with tempfile.TemporaryDirectory() as td:
            a = release.build_release(ROOT, CURRENT_VERSION, 'example/short-compass', Path(td) / 'a', notes_text='same')
            b = release.build_release(ROOT, CURRENT_VERSION, 'example/short-compass', Path(td) / 'b', notes_text='same')
            self.assertEqual(a['sha256'], b['sha256'])


    def test_workflow_actions_are_pinned_to_full_commit_shas(self):
        import re
        workflow = (ROOT / 'release_workflow_template.yml').read_text(encoding='utf-8')
        refs = re.findall(r'^\s*uses:\s*([^\s#]+)', workflow, flags=re.M)
        self.assertEqual(len(refs), 4, refs)
        for ref in refs:
            self.assertRegex(ref, r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$', ref)
        self.assertIn('persist-credentials: false', workflow)
        self.assertIn('contents: write', workflow)
        self.assertNotIn('softprops/action-gh-release@v2', workflow)
        self.assertNotIn("node-version: '20'", workflow)

    def test_manifest_minimum_version_cannot_exceed_release(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, 'minimumVersion'):
                release.build_release(ROOT, CURRENT_VERSION, 'example/short-compass', Path(td), minimum_version='2.46')


if __name__ == '__main__':
    unittest.main(verbosity=2)
