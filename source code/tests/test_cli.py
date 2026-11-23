#!/usr/bin/env python3
"""Exercise control commands without touching system services or APT."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
    d = Path(tmp)
    state = d / 'state.json'
    state.write_text(json.dumps({'regular': 2, 'security': 3, 'kernel_security': 1,
                                 'valid': 1, 'checked_at': 1793870000}))
    source = (ROOT / 'updates-monitor').read_text().replace('[[ $EUID == 0 ]]', '[[ 1 == 1 ]]')
    source = source.replace('/usr/local/lib/updates-monitor/scheduler.py', str(d / 'scheduler'))
    source = source.replace('/run/updates-monitor/state.json', str(state))
    (d / 'cli').write_text(source)
    fake = {
        'systemctl': '''printf "systemctl %s\\n" "$*" >> "$TEST_LOG"
case "$1" in
 start) [[ $* == *updates-monitor.service* ]] && exit "${TEST_START:-0}"; exit 0;;
 is-active) if [[ "$2" == cron.service ]]; then echo active; else echo inactive; fi;;
esac''',
        'scheduler': '''printf "scheduler %s\\n" "$*" >> "$TEST_LOG"
if [[ "$1" == show ]]; then printf '%s\\n' '{"enabled":true,"interval":"6h","cron_active":true}'; fi
if [[ "$1" == reboot-status ]]; then printf '%s\\n' "${TEST_REBOOT:-}"; fi
exit 0''',
        'journalctl': '''printf 'journalctl\\n' >> "$TEST_LOG"
echo 'Przykładowy błąd usługi' ''',
    }
    for name, body in fake.items():
        p = d / name
        p.write_text('#!/bin/bash\n' + body + '\n')
        p.chmod(0o755)
    env = dict(os.environ, PATH=tmp + ':' + os.environ['PATH'], TEST_LOG=str(d / 'log'), TEST_REBOOT=json.dumps({'reboot_required': 0, 'kernel_update_pending': 0}))
    for action in ('status',):
        (d / 'log').write_text('')
        result = subprocess.run(['bash', str(d / 'cli'), action], env=env, text=True, capture_output=True)
        lines = (d / 'log').read_text().splitlines()
        assert result.returncode == 0, (action, result.stdout, result.stderr)
        if action == 'status':
            assert 'Interwał:   6h' in result.stdout and 'Cron:       active' in result.stdout
            assert 'Regularne:' in result.stdout and 'Restart niewymagany' in result.stdout
            assert 'journalctl' not in lines
            assert not any(line.startswith('scheduler enable') for line in lines)
    for reboot, kernel, expected in [(1, 0, 'wymagany restart systemu'),
                                     (0, 1, 'wymagany restart systemu'),
                                     (0, 2, 'Stan nieznany')]:
        env['TEST_REBOOT'] = json.dumps({'reboot_required': reboot, 'kernel_update_pending': kernel})
        result = subprocess.run(['bash', str(d / 'cli'), 'status'], env=env, text=True, capture_output=True)
        assert result.returncode == 0 and expected in result.stdout, (result.stdout, result.stderr)
    env['TEST_REBOOT'] = json.dumps({'reboot_required': 0, 'kernel_update_pending': 0})
    (d / 'log').write_text('')
    for removed_action in ('start', 'stop'):
        result = subprocess.run(['bash', str(d / 'cli'), removed_action], env=env, text=True, capture_output=True)
        assert result.returncode == 2 and (d / 'log').read_text() == ''
    (d / 'log').write_text('')
    result = subprocess.run(['bash', str(d / 'cli'), 'interval', '30D'], env=env, text=True, capture_output=True)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert (d / 'log').read_text().splitlines() == [
        'scheduler interval 30D', 'scheduler enable 1', 'systemctl start --no-block updates-monitor-scheduler.service']
    (d / 'log').write_text('')
    disabled = subprocess.run(['bash', str(d / 'cli'), 'interval', '0'], env=env, text=True, capture_output=True)
    assert disabled.returncode == 0 and 'wyłączone' in disabled.stdout
    assert (d / 'log').read_text().splitlines() == [
        'scheduler enable 0', 'systemctl start --no-block updates-monitor-scheduler.service']
    env['TEST_START'] = '1'
    result = subprocess.run(['bash', str(d / 'cli'), 'status'], env=env, text=True, capture_output=True)
    assert result.returncode == 1 and 'Przykładowy błąd usługi' in result.stdout
print('OK: status, interwał i usunięte polecenia start i stop')
