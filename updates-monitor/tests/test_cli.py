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
[[ "$1" == show ]] && printf '%s\\n' '{"enabled":true,"interval":"6h","cron_active":true}'
exit 0''',
        'journalctl': '''printf 'journalctl\\n' >> "$TEST_LOG"
echo 'Przykładowy błąd usługi' ''',
    }
    for name, body in fake.items():
        p = d / name
        p.write_text('#!/bin/bash\n' + body + '\n')
        p.chmod(0o755)
    env = dict(os.environ, PATH=tmp + ':' + os.environ['PATH'], TEST_LOG=str(d / 'log'))
    for action in ('status',):
        (d / 'log').write_text('')
        result = subprocess.run(['bash', str(d / 'cli'), action], env=env, text=True, capture_output=True)
        lines = (d / 'log').read_text().splitlines()
        assert result.returncode == 0, (action, result.stdout, result.stderr)
        if action == 'status':
            assert 'Interwał kontroli: 6h' in result.stdout and 'Stan cron: active' in result.stdout
            assert 'Suma kontroli: aktualizacje regularne: 2' in result.stdout
            assert 'journalctl' not in lines
            assert not any(line.startswith('scheduler enable') for line in lines)
    (d / 'log').write_text('')
    for removed_action in ('start', 'stop'):
        result = subprocess.run(['bash', str(d / 'cli'), removed_action], env=env, text=True, capture_output=True)
        assert result.returncode == 2 and (d / 'log').read_text() == ''
    (d / 'log').write_text('')
    result = subprocess.run(['bash', str(d / 'cli'), 'interval', '15D'], env=env, text=True, capture_output=True)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert (d / 'log').read_text().splitlines() == [
        'scheduler interval 15D', 'systemctl start --no-block updates-monitor-scheduler.service']
    env['TEST_START'] = '1'
    result = subprocess.run(['bash', str(d / 'cli'), 'status'], env=env, text=True, capture_output=True)
    assert result.returncode == 1 and 'Przykładowy błąd usługi' in result.stdout
print('OK: status, interwał i usunięte polecenia start i stop')
