#!/usr/bin/env python3
"""Verify wrapper order and reinstall behavior with isolated fake commands."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp)
    source = (root / 'install-deb.sh').read_text().replace('[[ $EUID == 0 ]]', '[[ 1 == 1 ]]')
    (path / 'install-deb.sh').write_text(source)
    (path / 'updates-monitor_0.5.11-1_all.deb').write_text('test package')
    dpkg = path / 'dpkg-query'
    dpkg.write_text('#!/bin/bash\n[[ ${TEST_INSTALLED:-0} == 1 ]] && printf installed\n')
    apt = path / 'apt-get'
    apt.write_text('#!/bin/bash\nprintf "apt %s\\n" "$*" >> "$TEST_LOG"\n')
    dpkg.chmod(0o755)
    apt.chmod(0o755)
    env = dict(os.environ, PATH=tmp + ':' + os.environ['PATH'], TEST_LOG=str(path / 'log'))
    for installed in ('0', '1'):
        (path / 'log').write_text('')
        env['TEST_INSTALLED'] = installed
        result = subprocess.run(['bash', str(path / 'install-deb.sh')], env=env,
                                capture_output=True, text=True)
        lines = (path / 'log').read_text().splitlines()
        assert result.returncode == 0 and len(lines) == 1, (result, lines)
        assert lines[0].startswith('apt install -y '), lines
        assert ('--reinstall' in lines[0]) == (installed == '1'), lines
print('OK: instalacja i ponowna instalacja pakietu bez instalacji agenta')
