#!/usr/bin/env python3
"""Release detection stays independent from package counts and handles unknown states."""
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.modules['apt'] = types.SimpleNamespace()
spec = importlib.util.spec_from_file_location('distribution_check', ROOT / 'updates-monitor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def os_release(distro, version):
    return {'ID': distro, 'VERSION_ID': version, 'PRETTY_NAME': distro + ' ' + version}

with patch.object(m, 'read_os_release', return_value=os_release('debian', '13')):
    with patch.object(m, 'debian_release', return_value=(13, 'trixie')):
        assert m.distribution_status()['dist_upgrade_available'] == 0
    with patch.object(m, 'debian_release', return_value=(14, 'forky')):
        r = m.distribution_status()
        assert r['dist_upgrade_available'] == 1 and r['dist_upgrade_target'] == 'Debian 14 (forky)', r
    with patch.object(m, 'debian_release', side_effect=OSError('offline')):
        r = m.distribution_status()
        assert r['dist_upgrade_available'] == 2 and 'offline' in r['dist_upgrade_error'], r
with patch.object(m, 'read_os_release', return_value=os_release('debian', '12')):
    with patch.object(m, 'debian_release', side_effect=[(14, 'forky'), (13, 'trixie')]):
        r = m.distribution_status()
        assert r['dist_upgrade_available'] == 1 and r['dist_upgrade_target'] == 'Debian 13 (trixie)', r
with patch.object(m, 'read_os_release', return_value=os_release('debian', '10')):
    with patch.object(m, 'debian_release', side_effect=[(14, 'forky'), (13, 'trixie')]):
        assert m.distribution_status()['dist_upgrade_available'] == 2
with patch.object(m, 'read_os_release', return_value=os_release('debian', 'forky/sid')):
    assert m.distribution_status()['dist_upgrade_available'] == 2
with patch.object(m.urllib.request, 'urlopen', return_value=io.BytesIO(b'Origin: Debian\nSuite: stable\nVersion: 13.8\nCodename: trixie\n')):
    assert m.debian_release('stable') == (13, 'trixie')
for payload in [b'<html>error</html>', b'Origin: Other\nSuite: stable\nVersion: 14\nCodename: forky\n']:
    with patch.object(m.urllib.request, 'urlopen', return_value=io.BytesIO(payload)):
        try: m.debian_release('stable')
        except ValueError: pass
        else: raise AssertionError('Malformed release metadata accepted')
with patch.object(m, 'read_os_release', return_value=os_release('ubuntu', '22.04')):
    with patch.object(m.shutil, 'which', return_value='/usr/bin/do-release-upgrade'):
        for code, stdout, stderr, expected in [(0, "New release '24.04.1 LTS' available.\n", '', 1),
                                               (1, 'No new release found.\n', '', 0),
                                               (1, 'No new release found.\nFailed to connect', '', 2),
                                               (1, 'No new release found.\n', 'Network failure', 2),
                                               (2, '', 'Error', 2)]:
            with patch.object(m.subprocess, 'run', return_value=types.SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)) as command:
                r = m.distribution_status()
                assert r['dist_upgrade_available'] == expected, r
                assert command.call_args[0][0] == ['/usr/bin/do-release-upgrade', '-c']
        with patch.object(m.subprocess, 'run', side_effect=subprocess.TimeoutExpired('release-check', 90)):
            assert m.distribution_status()['dist_upgrade_available'] == 2
    with patch.object(m.shutil, 'which', return_value=None):
        assert m.distribution_status()['dist_upgrade_available'] == 2
with patch.object(m, 'read_os_release', return_value=os_release('other', '1')):
    assert m.distribution_status()['dist_upgrade_available'] == 2
print('OK: Debian, Ubuntu, next release only, point release, offline and invalid metadata')
