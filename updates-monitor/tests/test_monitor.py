#!/usr/bin/env python3
"""Test APT classification and cron scheduling without touching the host."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[1]


class Package:
    def __init__(self, name, archive, *, upgrade=False, install=False, installed=True):
        self.name = name
        self.candidate = types.SimpleNamespace(origins=[types.SimpleNamespace(archive=archive)])
        self.marked_upgrade = upgrade
        self.marked_install = install
        self.is_installed = installed


class Cache:
    def upgrade(self, dist_upgrade=False):
        assert dist_upgrade is True

    def get_changes(self):
        return [Package('curl', 'trixie', upgrade=True),
                Package('openssl', 'trixie-security', upgrade=True),
                Package('linux-image-amd64', 'trixie-security', upgrade=True),
                Package('linux-image-6.1.0-test', 'trixie-security', install=True, installed=False),
                Package('linux-headers-amd64', 'trixie', upgrade=True),
                Package('linux-image-6.2.0-test', 'trixie', install=True, installed=False),
                Package('new-dependency', 'trixie-security', install=True, installed=False),
                Package('held', 'trixie-security')]


sys.modules['apt'] = types.SimpleNamespace(Cache=Cache)
spec = importlib.util.spec_from_file_location('updates_check', ROOT / 'updates-monitor.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)
with tempfile.TemporaryDirectory() as temp:
    monitor.STATE = Path(temp) / 'state.json'
    real_run = monitor.subprocess.run
    monitor.subprocess.run = lambda *args, **kwargs: None
    data = monitor.check()
    monitor.subprocess.run = real_run
    assert [data[k] for k in ('regular', 'security', 'kernel_security', 'valid')] == [1, 1, 4, 1], data
    monitor.STATE.write_text(json.dumps({'regular': 3, 'security': 2, 'kernel_security': 1,
                                         'valid': 0, 'checked_at': 1}))
    fresh = {'regular': 5, 'security': 0, 'kernel_security': 4, 'valid': 1, 'checked_at': 2}
    combined = monitor.accumulate(fresh)
    assert [combined[k] for k in monitor.COUNT_KEYS] == [8, 0, 5], combined
    monitor.STATE.write_text(json.dumps(combined))
    combined = monitor.accumulate({'regular': 5, 'security': 0, 'kernel_security': 4})
    assert [combined[k] for k in monitor.COUNT_KEYS] == [13, 0, 9], combined
    monitor.STATE.write_text(json.dumps(combined))
    cleared = monitor.accumulate({'regular': 0, 'security': 0, 'kernel_security': 0})
    assert [cleared[k] for k in monitor.COUNT_KEYS] == [0, 0, 0], cleared

spec = importlib.util.spec_from_file_location('updates_scheduler', ROOT / 'updates-monitor-scheduler.py')
scheduler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scheduler)
with tempfile.TemporaryDirectory() as temp:
    d = Path(temp)
    scheduler.CONFIG = d / 'etc/schedule.json'
    scheduler.RUNTIME = d / 'run'
    scheduler.HEALTH = scheduler.RUNTIME / 'health.json'
    scheduler.LAST = scheduler.RUNTIME / 'last-attempt'
    scheduler.DPKG_SEEN = scheduler.RUNTIME / 'dpkg-status-signature'
    scheduler.DPKG_STATUS = d / 'dpkg-status'
    scheduler.DPKG_LOCKS = (d / 'lock-frontend', d / 'lock')
    scheduler.LEGACY = d / 'legacy.json'
    scheduler.CRON_FILE = d / 'cronfile'
    scheduler.CRON_FILE.write_text('* * * * * root /usr/bin/systemctl start --no-block updates-monitor-scheduler.service\n')
    scheduler.DPKG_STATUS.write_text('initial')
    for lock in scheduler.DPKG_LOCKS: lock.touch()
    calls = []
    state = {'service': 'inactive', 'cron': True, 'now': 59}
    def command(*args, check=True):
        if args[0] == 'cat': return types.SimpleNamespace(returncode=1, stdout='')
        if args[0] == 'is-active': return types.SimpleNamespace(returncode=0 if state['cron'] else 3, stdout='')
        if args[0] == 'show': return types.SimpleNamespace(returncode=0, stdout=state['service'])
        if args[0] == 'start': calls.append(args); return types.SimpleNamespace(returncode=0, stdout='')
        raise AssertionError(args)
    scheduler.command = command
    scheduler.time.monotonic = lambda: state['now']
    scheduler.init()
    assert scheduler.load() == {'enabled': True, 'interval': '1D'}
    scheduler.tick()
    assert not calls
    state['now'] = 61
    scheduler.tick()
    assert len(calls) == 1
    state['now'] = 3659
    scheduler.tick()
    assert len(calls) == 1
    state['now'] = 86461
    scheduler.tick()
    assert len(calls) == 2
    for interval, seconds in scheduler.INTERVALS.items():
        scheduler.save({'enabled': True, 'interval': interval})
        scheduler.LAST.write_text('100')
        state['now'] = 100 + seconds - 1
        before = len(calls)
        scheduler.tick()
        assert len(calls) == before, interval
        state['now'] += 1
        scheduler.tick()
        assert len(calls) == before + 1, interval
    scheduler.save({'enabled': True, 'interval': '1D'})
    scheduler.LAST.write_text('1000')
    state['now'] = 1100
    before = len(calls)
    scheduler.DPKG_STATUS.write_text('packages installed')
    locker = subprocess.Popen([sys.executable, '-c',
        'import fcntl,sys; f=open(sys.argv[1],"r+"); fcntl.lockf(f,fcntl.LOCK_EX); print("locked",flush=True); sys.stdin.readline()',
        str(scheduler.DPKG_LOCKS[0])], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert locker.stdout.readline().strip() == 'locked'
        scheduler.tick()
        assert len(calls) == before, 'Package manager lock must delay the check'
    finally:
        locker.stdin.write('\n'); locker.stdin.flush(); locker.wait(timeout=5)
    state['service'] = 'active'
    scheduler.tick()
    assert len(calls) == before, 'An active check must not consume the change'
    state['service'] = 'inactive'
    scheduler.tick()
    assert len(calls) == before + 1, 'Package changes must trigger a check without reboot'
    state['now'] += 60
    scheduler.tick()
    assert len(calls) == before + 1, 'Unchanged package state must not trigger a second check'
    scheduler.save({'enabled': False, 'interval': '10D'})
    state['service'] = 'failed'
    before = len(calls)
    scheduler.tick()
    h = json.loads(scheduler.HEALTH.read_text())
    assert h['scheduler_active'] == 0 and h['service_failed'] == 1 and h['interval_seconds'] == 864000, h
    assert len(calls) == before
    scheduler.save({'enabled': True, 'interval': '2h'})
    state['cron'] = False
    scheduler.tick()
    h = json.loads(scheduler.HEALTH.read_text())
    assert h['scheduler_active'] == 0 and len(calls) == before
    scheduler.CONFIG.unlink()
    scheduler.LEGACY.write_text(json.dumps({'enabled': False, 'interval': '15h'}))
    scheduler.init()
    assert scheduler.load() == {'enabled': False, 'interval': '12h'} and not scheduler.LEGACY.exists()
    scheduler.CONFIG.unlink()
    def old_timer(*args, check=True):
        if args[0] == 'cat':
            return types.SimpleNamespace(returncode=0, stdout='OnUnitActiveSec=1h\nOnUnitActiveSec=\nOnUnitActiveSec=3d\n')
        if args[0] == 'is-enabled': return types.SimpleNamespace(returncode=0, stdout='')
        raise AssertionError(args)
    scheduler.command = old_timer
    scheduler.init()
    assert scheduler.load() == {'enabled': True, 'interval': '5D'}
    for old, new in scheduler.LEGACY_INTERVALS.items():
        scheduler.CONFIG.write_text(json.dumps({'enabled': False, 'interval': old}))
        scheduler.init()
        assert scheduler.load() == {'enabled': False, 'interval': new}
print('OK: APT, cron po starcie, interwał i wyłączony harmonogram')
