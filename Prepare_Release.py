# -*- coding: utf-8 -*-
"""Build a reproducible ShortCompass release ZIP and update manifest (stdlib only)."""
from __future__ import print_function
import argparse
import ast
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

CORE_FILES = ('ShortCompass.html', 'ShortCompassServer.py', 'Start_ShortCompass.bat', 'Start_ShortCompass_Server.bat')
VERSION_RE = re.compile(r'^\d+(?:\.\d+){1,3}$')
REPOSITORY_RE = re.compile(r'^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$')
SECRET_PATTERNS = (
    ('OpenAI-like API key', re.compile(r'\bsk-[A-Za-z0-9_-]{32,}\b')),
    ('Anthropic-like API key', re.compile(r'\bsk-ant-[A-Za-z0-9_-]{24,}\b')),
    ('Google API key', re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b')),
    ('private key header', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
)


def version_tuple(value):
    value = str(value or '').strip().lstrip('vV')
    if not VERSION_RE.fullmatch(value):
        raise ValueError('버전은 2.40 또는 2.40.1처럼 숫자와 점으로 입력해야 합니다.')
    parts = tuple(int(part) for part in value.split('.'))
    return parts + (0,) * (4 - len(parts))


def validate_repository(value):
    value = str(value or '').strip()
    parts=value.split('/')
    if (not REPOSITORY_RE.fullmatch(value) or len(parts)!=2 or
        parts[0].upper() in ('OWNER','YOUR-OWNER','YOUR_OWNER') or
        parts[1].upper() in ('REPOSITORY','REPO','YOUR-REPOSITORY','YOUR_REPOSITORY')):
        raise ValueError('GitHub 저장소는 실제 OWNER/REPOSITORY 형식으로 입력하세요.')
    return value


def allowed_package_files(server_path):
    tree = ast.parse(Path(server_path).read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == 'UPDATE_ALLOWED_FILES' for target in targets):
                values = ast.literal_eval(node.value)
                if not isinstance(values, set) or not values:
                    raise ValueError('서버 UPDATE_ALLOWED_FILES 목록이 올바르지 않습니다.')
                for name in values:
                    if not isinstance(name, str) or Path(name).name != name or name in ('.', '..'):
                        raise ValueError('업데이트 허용 목록에 잘못된 경로가 있습니다: '+str(name))
                return sorted(values)
    raise ValueError('서버의 UPDATE_ALLOWED_FILES 목록을 찾을 수 없습니다.')


def scan_for_secrets(source_root, files):
    issues = []
    for name in files:
        path = Path(source_root) / name
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeError):
            continue
        for label, pattern in SECRET_PATTERNS:
            match = pattern.search(text)
            if match:
                # Never print the match itself; only disclose the file and pattern category.
                issues.append({'file': name, 'type': label})
                break
    return issues


def validate_source_tree(source_root, version):
    source_root = Path(source_root).resolve()
    version = str(version).strip().lstrip('vV')
    version_tuple(version)
    server_path = source_root / 'ShortCompassServer.py'
    if not server_path.is_file():
        raise ValueError('ShortCompassServer.py를 찾을 수 없습니다.')
    server_text = server_path.read_text(encoding='utf-8')
    match = re.search(r"^APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]", server_text, re.M)
    if not match or match.group(1) != version:
        raise ValueError('요청 버전과 서버 APP_VERSION이 일치하지 않습니다. server='+str(match.group(1) if match else 'missing'))
    html_text = (source_root / 'ShortsCompass.html').read_text(encoding='utf-8') if (source_root / 'ShortsCompass.html').is_file() else ''
    title = re.search(r'<title>[^<]*?v([0-9]+(?:\.[0-9]+){1,3})', html_text, re.I)
    footer = re.search(r'class=["\']footer["\'][^>]*>[^<]*?v([0-9]+(?:\.[0-9]+){1,3})', html_text, re.I)
    backup = re.search(r"backupMeta:\{app:'ShortCompass',version:'([0-9]+(?:\.[0-9]+){1,3})'", html_text)
    if any(not m or m.group(1) != version for m in (title, footer, backup)):
        raise ValueError('HTML 제목·하단·백업 메타데이터의 버전이 요청 버전과 일치하지 않습니다.')
    files = allowed_package_files(server_path)
    missing = [name for name in files if not (source_root / name).is_file()]
    if missing:
        raise ValueError('업데이트 허용 파일 목록 중 누락된 파일이 있습니다: '+', '.join(missing))
    for name in files:
        if (source_root / name).stat().st_size == 0:
            raise ValueError('빈 파일은 릴리스 패키지에 포함할 수 없습니다: '+name)
    secrets = scan_for_secrets(source_root, files)
    if secrets:
        items = ', '.join(x['file']+' ('+x['type']+')' for x in secrets)
        raise ValueError('잠재적 비밀정보가 발견되어 릴리스를 중단했습니다: '+items+'. 파일에서 키/개인키를 제거하고 다시 실행하세요.')
    return source_root, files


def build_release(source_root, version, repository, output_dir, minimum_version='2.38', notes_text=None, notes_file=None):
    version = str(version).strip().lstrip('vV')
    version_tuple(version)
    repository = validate_repository(repository)
    minimum_version = str(minimum_version or '2.38').strip().lstrip('vV')
    if version_tuple(minimum_version) > version_tuple(version):
        raise ValueError('minimumVersion은 릴리스 version보다 클 수 없습니다.')
    source_root, files = validate_source_tree(source_root, version)
    if notes_text is None and notes_file:
        notes_text = Path(notes_file).read_text(encoding='utf-8')
    elif notes_text is None:
        default_notes = source_root / 'RELEASE_NOTES_CURRENT_KO.txt'
        notes_text = default_notes.read_text(encoding='utf-8') if default_notes.is_file() else '숏폼 나침반 '+version+' 업데이트'
    notes_text = str(notes_text or '').strip()[:5000]
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    package_name = 'ShortCompass-v'+version+'.zip'
    package_path = output_dir / package_name
    feed_url = 'https://github.com/{}/releases/latest/download/update_manifest.json'.format(repository)
    with zipfile.ZipFile(str(package_path), 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in files:
            payload = (source_root / name).read_bytes()
            if name == 'ShortCompassServer.py':
                server_text = payload.decode('utf-8')
                server_text, replace_count = re.subn(
                    r"(?m)^DEFAULT_UPDATE_MANIFEST_URL\s*=\s*(['\"])(.*?)\1\s*$",
                    'DEFAULT_UPDATE_MANIFEST_URL = ' + json.dumps(feed_url),
                    server_text,
                    count=1,
                )
                if replace_count != 1:
                    raise ValueError('ShortCompassServer.py의 DEFAULT_UPDATE_MANIFEST_URL 자리표시자를 찾을 수 없습니다.')
                payload = server_text.encode('utf-8')
            # Windows CMD batch files need CRLF; normalize even when release is built on Linux.
            if name.lower().endswith('.bat'):
                payload = payload.replace(b'\r\n', b'\n').replace(b'\r', b'\n').replace(b'\n', b'\r\n')
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    digest = hashlib.sha256(package_path.read_bytes()).hexdigest()
    download_url = 'https://github.com/{}/releases/download/v{}/{}'.format(repository, version, package_name)
    manifest = {
        'schemaVersion': 1,
        'version': version,
        'minimumVersion': minimum_version,
        'downloadUrl': download_url,
        'sha256': digest,
        'releaseNotes': notes_text,
        'builtAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    }
    manifest_path = output_dir / 'update_manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    sums_path = output_dir / 'SHA256SUMS.txt'
    sums_path.write_text('{}  {}\n'.format(digest, package_name), encoding='ascii')
    # Self-check outputs before declaring success.
    with zipfile.ZipFile(str(package_path), 'r') as archive:
        names = archive.namelist()
        if names != files:
            raise ValueError('생성 ZIP의 파일 목록이 허용 목록과 일치하지 않습니다.')
        bad = archive.testzip()
        if bad:
            raise ValueError('생성 ZIP 무결성 검사 실패: '+bad)
    reread = json.loads(manifest_path.read_text(encoding='utf-8'))
    if reread['sha256'] != hashlib.sha256(package_path.read_bytes()).hexdigest():
        raise ValueError('manifest SHA-256 자체 검증에 실패했습니다.')
    return {'packagePath': str(package_path), 'manifestPath': str(manifest_path), 'sumsPath': str(sums_path),
            'sha256': digest, 'fileCount': len(files), 'version': version,
            'manifestUrl': 'https://github.com/{}/releases/latest/download/update_manifest.json'.format(repository),
            'downloadUrl': download_url}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build a verified ShortCompass ZIP, update manifest, and SHA256SUMS.')
    parser.add_argument('--version', required=True, help='Release version without or with v prefix, e.g. 2.40')
    parser.add_argument('--repository', required=True, help='GitHub OWNER/REPOSITORY')
    parser.add_argument('--source', default=str(Path(__file__).resolve().parent), help='Source directory')
    parser.add_argument('--output', default='dist', help='Output directory')
    parser.add_argument('--minimum-version', default='2.38', help='Oldest supported installed version')
    parser.add_argument('--notes-file', default='RELEASE_NOTES_CURRENT_KO.txt', help='Release notes text file')
    args = parser.parse_args(argv)
    try:
        source = Path(args.source).resolve()
        notes_path = Path(args.notes_file)
        if not notes_path.is_absolute(): notes_path = source / notes_path
        result = build_release(source, args.version, args.repository, args.output, args.minimum_version, notes_file=notes_path)
        print('릴리스 ZIP 생성 및 검증 완료')
        print('버전: '+result['version'])
        print('파일 수: '+str(result['fileCount']))
        print('ZIP: '+result['packagePath'])
        print('SHA-256: '+result['sha256'])
        print('manifest: '+result['manifestPath'])
        print('업데이트 센터에 등록할 안정 manifest URL: '+result['manifestUrl'])
        print('주의: URL은 공개 GitHub Release에 manifest를 게시한 뒤에만 사용 가능합니다.')
        return 0
    except Exception as e:
        print('릴리스 준비 실패: '+str(e), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
