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
trigger = next(t for t in data['triggers'] if t['name'] == 'Wymagany restart systemu po aktualizacji')
assert '{HOST.NAME}' in trigger['event_name']
assert trigger['recovery_expression'].endswith(')=0')
assert (root / 'zabbix-updates-monitor.json').read_bytes() == (root.parent / 'template/updates-monitor.json').read_bytes()
print('OK: reboot marker, DNF, błędy oraz szablon Zabbiksa')
