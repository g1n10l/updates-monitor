#!/usr/bin/env python3
"""Exercise reboot detection and Zabbix contract without changing the host."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('scheduler_reboot', root / 'updates-monitor-scheduler.py')
scheduler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scheduler)
with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    scheduler.DPKG_STATUS = base / 'dpkg-status'
    scheduler.REBOOT_MARKER = base / 'reboot-required'
    scheduler.DNF = base / 'dnf'
    assert scheduler.reboot_required() == 2
    scheduler.DPKG_STATUS.touch()
    assert scheduler.reboot_required() == 0
    scheduler.REBOOT_MARKER.touch()
    assert scheduler.reboot_required() == 1
    scheduler.REBOOT_MARKER.unlink()
    assert scheduler.reboot_required() == 0
    scheduler.DPKG_STATUS.unlink()
    scheduler.DNF.touch()
    for code, output, expected in [(0, 'Reboot should not be necessary.', 0),
                                   (1, 'Reboot is required to fully utilize these updates.', 1),
                                   (1, 'Error: command not found', 2),
                                   (2, '', 2)]:
        with patch.object(scheduler.subprocess, 'run', return_value=SimpleNamespace(returncode=code, stdout=output)):
            assert scheduler.reboot_required() == expected
    with patch.object(scheduler.subprocess, 'run', side_effect=subprocess.TimeoutExpired('dnf', 45)):
        assert scheduler.reboot_required() == 2

with tempfile.TemporaryDirectory() as tmp:
    scheduler.BOOT_DIR = Path(tmp)
    kernel = lambda: SimpleNamespace(release='6.8.0-40-generic')
    def version_sort(args, **kw):
        import re
        values = kw['input'].splitlines()
        def key(v):
            return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', v)]
        return SimpleNamespace(stdout='\n'.join(sorted(values, key=key)) + '\n')
    with patch.object(scheduler.os, 'uname', kernel), patch.object(scheduler.subprocess, 'run', side_effect=version_sort):
        assert scheduler.kernel_update_pending() == 2
        (scheduler.BOOT_DIR / 'vmlinuz-6.8.0-40-generic').touch()
        assert scheduler.kernel_update_pending() == 0
        (scheduler.BOOT_DIR / 'vmlinuz-6.8.0-42-lowlatency').touch()
        assert scheduler.kernel_update_pending() == 0
        (scheduler.BOOT_DIR / 'vmlinuz-6.8.0-41-generic').touch()
        assert scheduler.kernel_update_pending() == 1
    trixie_running = lambda: SimpleNamespace(release='6.12.118+deb13-amd64')
    (scheduler.BOOT_DIR / 'vmlinuz-6.12.118+deb13-amd64').touch()
    with patch.object(scheduler.os, 'uname', trixie_running), patch.object(scheduler.subprocess, 'run', side_effect=version_sort):
        assert scheduler.kernel_update_pending() == 0
        (scheduler.BOOT_DIR / 'vmlinuz-6.12.119+deb13-amd64').touch()
        assert scheduler.kernel_update_pending() == 1
    rpm_running = lambda: SimpleNamespace(release='5.14.0-427.13.1.el9_4.x86_64')
    (scheduler.BOOT_DIR / 'vmlinuz-5.14.0-427.22.1.el9_4.x86_64').touch()
    with patch.object(scheduler.os, 'uname', rpm_running), patch.object(scheduler.subprocess, 'run', side_effect=version_sort):
        assert scheduler.kernel_update_pending() == 1
    with patch.object(scheduler.os, 'uname', lambda: SimpleNamespace(release='unsupported')):
        assert scheduler.kernel_update_pending() == 2

with tempfile.TemporaryDirectory() as tmp:
    import os
    base = Path(tmp)
    scheduler.STATE = base / 'state.json'
    scheduler.DPKG_STATUS = base / 'dpkg-status'
    scheduler.DPKG_LOCKS = (base / 'lock',)
    scheduler.RPM_DATABASES = ()
    scheduler.DPKG_STATUS.touch()
    os.utime(scheduler.DPKG_STATUS, (1000, 1000))
    scheduler.STATE.write_text(json.dumps({'valid': 1, 'checked_at': 999}))
    assert scheduler.package_scan_current() == 0
    scheduler.STATE.write_text(json.dumps({'valid': 1, 'checked_at': 1000}))
    assert scheduler.package_scan_current() == 0
    scheduler.STATE.write_text(json.dumps({'valid': 1, 'checked_at': 1001}))
    assert scheduler.package_scan_current() == 1
    scheduler.STATE.write_text(json.dumps({'valid': 0, 'checked_at': 1001}))
    assert scheduler.package_scan_current() == 0

data = json.loads((root / 'zabbix-updates-monitor.json').read_text())['zabbix_export']
items = {i['key']: i for i in data['templates'][0]['items']}
item = items['updates.monitor.reboot_required']
assert item['master_item']['key'] == 'updates.monitor.health'
js = item['preprocessing'][0]['parameters'][0]
harness = 'var f = new Function("value", process.argv[1]); console.log(JSON.stringify(f(process.argv[2])));'
for value, expected in [({'valid': 1, 'reboot_required': 0}, '0'),
                        ({'valid': 1, 'reboot_required': 1}, '1'),
                        ({'valid': 1, 'reboot_required': 2}, '2'),
                        ({'valid': 0, 'reboot_required': 0}, '2'),
                        ({'valid': 1}, '2')]:
    actual = subprocess.check_output(['node', '-e', harness, js, json.dumps(value)], text=True).strip()
    assert actual == expected, (value, actual)
combined = items['updates.monitor.restart_needed']
js = combined['preprocessing'][0]['parameters'][0]
for a, b, expected in [(0, 0, '0'), (1, 0, '1'), (0, 1, '1'), (1, 2, '1'), (0, 2, '2'), (2, 2, '2')]:
    value = {'valid': 1, 'reboot_required': a, 'kernel_update_pending': b}
    actual = subprocess.check_output(['node', '-e', harness, js, json.dumps(value)], text=True).strip()
    assert actual == expected, (value, actual)
assert subprocess.check_output(['node', '-e', harness, js, json.dumps({'valid': 0, 'reboot_required': 1})], text=True).strip() == '2'
trigger = next(t for t in data['triggers'] if t['name'] == 'Wymagany restart hosta')
assert '{HOST.NAME}' in trigger['event_name']
assert 'updates.monitor.restart_needed)=1' in trigger['expression']
assert 'updates.monitor.valid)=1' in trigger['expression']
for category in ('regular', 'security', 'kernel_security'):
    assert 'updates.monitor.' + category + ')=0' in trigger['expression']
assert 'updates.monitor.restart_needed)=0' in trigger['recovery_expression']
assert 'updates.monitor.package_scan_current)=1' in trigger['expression']
assert 'updates.monitor.health.service_state)=0' in trigger['expression']
assert (root / 'zabbix-updates-monitor.json').read_bytes() == (root.parent / 'template/updates-monitor.json').read_bytes()
print('OK: reboot marker, DNF, błędy oraz szablon Zabbiksa')

kernel_item = items['updates.monitor.kernel_update_pending']
assert kernel_item['master_item']['key'] == 'updates.monitor.health'
kernel_trigger = next(t for t in data['triggers'] if t['uuid'] == 'b88e5c0862bc4deea324c25cdfef7000')
assert kernel_trigger['status'] == 'DISABLED'
