#!/usr/bin/env python3
"""Verify that corrupt downloads cannot reach apt."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp)
    source = (root / 'install-deb.sh').read_text().replace('[[ $EUID == 0 ]]', '[[ 1 == 1 ]]')
    wrapper = path / 'install-deb.sh'
    wrapper.write_text(source)
    package = path / 'updates-monitor_0.5.17-2_all.deb'
    package.write_text('test package')
    checksum = path / (package.name + '.sha256')
    original = hashlib.sha256(package.read_bytes()).hexdigest() + '  ' + package.name + '\n'
    checksum.write_text(original)
    commands = {
        'dpkg-query': '#!/bin/bash\n[[ ${TEST_INSTALLED:-0} == 1 ]] && printf installed\n',
        'apt-get': '#!/bin/bash\nprintf "apt %s\\n" "$*" >> "$TEST_LOG"\n',
        'dpkg-deb': '#!/bin/bash\n[[ ${TEST_BAD_DEB:-0} == 0 ]] || exit 2\nif [[ $1 == --field ]]; then printf "%s\\n" "${TEST_PACKAGE_NAME:-updates-monitor}"; fi\n',
    }
    for name, body in commands.items():
        command = path / name
        command.write_text(body)
        command.chmod(0o755)
    env = dict(os.environ, PATH=tmp + ':' + os.environ['PATH'], TEST_LOG=str(path / 'log'))
    for installed in ('0', '1'):
        (path / 'log').write_text('')
        env['TEST_INSTALLED'] = installed
        result = subprocess.run(['bash', str(wrapper)], env=env, capture_output=True, text=True)
        lines = (path / 'log').read_text().splitlines()
        assert result.returncode == 0 and len(lines) == 1, (result, lines)
        assert lines[0].startswith('apt install -y '), lines
        assert ('--reinstall' in lines[0]) == (installed == '1'), lines
    for scenario in ('missing-checksum', 'invalid-checksum', 'mismatch', 'invalid-archive', 'wrong-package'):
        checksum.write_text(original)
        env.pop('TEST_BAD_DEB', None)
        env.pop('TEST_PACKAGE_NAME', None)
        (path / 'log').write_text('')
        if scenario == 'missing-checksum': checksum.unlink()
        elif scenario == 'invalid-checksum': checksum.write_text('bad sum')
        elif scenario == 'mismatch': checksum.write_text('0' * 64 + '  ' + package.name + '\n')
        elif scenario == 'invalid-archive': env['TEST_BAD_DEB'] = '1'
        else: env['TEST_PACKAGE_NAME'] = 'another-package'
        result = subprocess.run(['bash', str(wrapper)], env=env, capture_output=True, text=True)
        assert result.returncode != 0 and not (path / 'log').read_text(), (scenario, result)
print('OK: install, reinstall, SHA-256 failures, invalid archive and wrong package')
