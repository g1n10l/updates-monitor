#!/usr/bin/python3
"""Cron-driven scheduler and status publisher for updates-monitor."""
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

CONFIG = Path('/etc/updates-monitor/schedule.json')
RUNTIME = Path('/run/updates-monitor')
HEALTH = RUNTIME / 'health.json'
STATE = RUNTIME / 'state.json'
RPM_DATABASES = (Path('/usr/lib/sysimage/rpm/rpmdb.sqlite'), Path('/var/lib/rpm/rpmdb.sqlite'))
LAST = RUNTIME / 'last-attempt'
LEGACY = Path('/var/lib/updates-monitor/legacy-schedule.json')
CRON_FILE = Path('/etc/cron.d/updates-monitor')
DPKG_STATUS = Path('/var/lib/dpkg/status')
REBOOT_MARKER = Path('/run/reboot-required')
DNF = Path('/usr/bin/dnf')
BOOT_DIR = Path('/boot')
DPKG_LOCKS = (Path('/var/lib/dpkg/lock-frontend'), Path('/var/lib/dpkg/lock'))
DPKG_SEEN = RUNTIME / 'dpkg-status-signature'
INTERVALS = {'2h': 7200, '6h': 21600, '12h': 43200, '1D': 86400, '5D': 432000, '10D': 864000, '15D': 1296000, '30D': 2592000}
LEGACY_INTERVALS = {'1h': '2h', '15h': '12h', '1d': '1D', '3d': '5D', '8d': '10D'}


def command(*args, check=True):
    return subprocess.run(['/usr/bin/systemctl', *args], text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=20, check=check)


def restore_context(path):
    """Label runtime files when SELinux tools are available.

    A permissive selinuxfs can remain mounted after SELinux packages are removed.
    Missing tools must not prevent monitoring in that state.
    """
    enforce = Path('/sys/fs/selinux/enforce')
    tool = Path('/usr/sbin/restorecon')
    if not enforce.exists():
        return
    if not tool.exists() and enforce.read_text().strip() == '0':
        return
    subprocess.run([str(tool), str(path)], check=True)


def atomic(path, content, mode=0o644):
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    if path.parent == RUNTIME:
        restore_context(path.parent)
    fd, tmp = tempfile.mkstemp(prefix='.updates-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            out.write(content)
            out.write('\n')
        os.chmod(tmp, mode)
        os.replace(tmp, path)
        if path.parent == RUNTIME:
            restore_context(path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load():
    data = json.loads(CONFIG.read_text(encoding='utf-8'))
    if type(data.get('enabled')) is not bool or data.get('interval') not in INTERVALS:
        raise ValueError('Nieprawidłowa konfiguracja harmonogramu')
    return data


def save(data):
    atomic(CONFIG, json.dumps(data, separators=(',', ':')))


def init():
    if CONFIG.exists():
        data = json.loads(CONFIG.read_text(encoding='utf-8'))
        interval = data.get('interval')
        if interval in LEGACY_INTERVALS:
            data['interval'] = LEGACY_INTERVALS[interval]
            if type(data.get('enabled')) is not bool:
                raise ValueError('Nieprawidłowa konfiguracja harmonogramu')
            save(data)
        else:
            load()
        return
    data = {'enabled': True, 'interval': '1D'}
    if LEGACY.exists():
        legacy = json.loads(LEGACY.read_text(encoding='utf-8'))
        legacy['interval'] = LEGACY_INTERVALS.get(legacy.get('interval'), legacy.get('interval'))
        if type(legacy.get('enabled')) is bool and legacy.get('interval') in INTERVALS:
            data = legacy
    else:
        old = command('cat', 'updates-monitor.timer', check=False)
        if old.returncode == 0:
            values = re.findall(r'^[ \t]*OnUnitActiveSec[ \t]*=[ \t]*([^\r\n]*)', old.stdout, re.MULTILINE)
            value = next((v.strip() for v in reversed(values) if v.strip()), '1h')
            data['interval'] = LEGACY_INTERVALS.get(value, value if value in INTERVALS else '1D')
            data['enabled'] = command('is-enabled', '--quiet', 'updates-monitor.timer', check=False).returncode == 0
    save(data)
    if LEGACY.exists():
        LEGACY.unlink()


def reboot_required():
    """Return 0=no marker, 1=reboot required, 2=unknown/error."""
    try:
        if DPKG_STATUS.is_file():
            return int(REBOOT_MARKER.is_file())
        if not DNF.is_file():
            return 2
        result = subprocess.run([str(DNF), '--disablerepo=*', 'needs-restarting', '-r'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, timeout=45,
                                env=dict(os.environ, LC_ALL='C'))
        # DNF also returns 1 for errors: accept only its explicit reboot hint.
        if result.returncode == 0 and 'Reboot should not be necessary.' in result.stdout:
            return 0
        if result.returncode == 1 and 'Reboot is required to fully utilize these updates.' in result.stdout:
            return 1
    except (OSError, subprocess.SubprocessError) as exc:
        print('Nie można sprawdzić restartu:', exc, file=sys.stderr)
    return 2


def kernel_update_pending():
    """Compare running kernel with boot images of the same flavour and architecture.

    0: no newer matching image, 1: newer image, 2: comparison unavailable.
    The boot images may include manually installed or retained kernels; this is
    a recommendation, not a guarantee that the bootloader will select one.
    """
    try:
        running = os.uname().release
        match = re.fullmatch(r'\d+(?:\.\d+)+(?:[+~.][0-9a-zA-Z.]+)?(?:-\d+)?(-[a-zA-Z][a-zA-Z0-9_-]*)', running)
        if match:
            suffix = match.group(1)
            family = lambda version: bool(re.fullmatch(r'\d+(?:\.\d+)+(?:[+~.][0-9a-zA-Z.]+)?(?:-\d+)?' + re.escape(suffix), version))
        else:
            match = re.fullmatch(r'\d+(?:\.\d+)+-\d+[a-zA-Z0-9_.+-]*\.(x86_64|aarch64|ppc64le|s390x)', running)
            if not match:
                return 2
            suffix = '.' + match.group(1)
            family = lambda version: version.endswith(suffix) and bool(re.fullmatch(r'\d[0-9a-zA-Z_.+-]*', version))
        images = [p.name[len('vmlinuz-'):] for p in BOOT_DIR.glob('vmlinuz-*') if p.is_file()]
        images = [v for v in images if family(v)]
        if not images:
            return 2
        versions = sorted(set(images + [running]))
        ordered = subprocess.run(['/usr/bin/sort', '-V'], input='\n'.join(versions) + '\n',
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 universal_newlines=True, check=True, timeout=10,
                                 env=dict(os.environ, LC_ALL='C')).stdout.splitlines()
        if len(ordered) != len(versions) or set(ordered) != set(versions):
            return 2
        return int(ordered[-1] != running)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print('Nie można porównać wersji kernela:', exc, file=sys.stderr)
        return 2


def package_scan_current():
    """A zero result is usable only after a scan newer than the package database."""
    locks = []
    try:
        state = json.loads(STATE.read_text(encoding='utf-8'))
        checked = state.get('checked_at')
        if state.get('valid') != 1 or type(checked) is not int or checked <= 0:
            return 0
        if DPKG_STATUS.is_file():
            for path in DPKG_LOCKS:
                try:
                    lock = path.open('r+')
                except FileNotFoundError:
                    continue
                locks.append(lock)
                try:
                    fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return 0
            database = DPKG_STATUS
        else:
            database = next((path for path in RPM_DATABASES if path.is_file()), None)
            if database is None:
                return 0
        changed = database.stat().st_mtime
        if database != DPKG_STATUS:
            wal = Path(str(database) + '-wal')
            if wal.exists():
                changed = max(changed, wal.stat().st_mtime)
        # checked_at has one-second resolution. Equality is ambiguous.
        return int(checked > changed)
    except (OSError, ValueError, TypeError):
        return 0
    finally:
        for lock in locks:
            lock.close()


def health(data):
    cron = command('is-active', '--quiet', 'cron.service', check=False).returncode == 0
    unit = command('show', 'updates-monitor.service', '--property=ActiveState', '--value').stdout.strip()
    states = {'inactive': 0, 'activating': 1, 'active': 2, 'deactivating': 3, 'failed': 4}
    if unit not in states:
        raise ValueError('Nieznany stan usługi: ' + unit)
    cron_configured = CRON_FILE.is_file() and any(
        line.lstrip().startswith('* * * * * ') and 'updates-monitor-scheduler.service' in line
        for line in CRON_FILE.read_text().splitlines())
    return {'valid': 1, 'scheduler_active': int(data['enabled'] and cron and cron_configured),
            'service_state': states[unit], 'service_failed': int(unit == 'failed'),
            'interval_seconds': INTERVALS[data['interval']], 'updated_at': int(time.time()),
            'reboot_required': reboot_required(), 'kernel_update_pending': kernel_update_pending(),
            'package_scan_current': package_scan_current()}


def dpkg_snapshot():
    """Detect a changed package database after package manager locks are released."""
    if not DPKG_STATUS.exists():
        return None, False, True
    locks = []
    try:
        for path in DPKG_LOCKS:
            try:
                lock = path.open('r+')
            except FileNotFoundError:
                continue
            locks.append(lock)
            try:
                fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return None, False, False
        stat = DPKG_STATUS.stat()
        signature = f'{stat.st_ino}:{stat.st_size}:{stat.st_mtime_ns}'
        try:
            old = DPKG_SEEN.read_text().strip()
        except FileNotFoundError:
            atomic(DPKG_SEEN, signature)
            return signature, False, True
        return signature, old != signature, True
    finally:
        for lock in locks:
            lock.close()


def tick():
    RUNTIME.mkdir(mode=0o755, parents=True, exist_ok=True)
    with (RUNTIME / 'scheduler.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        try:
            settings = load()
            status = health(settings)
            atomic(HEALTH, json.dumps(status, separators=(',', ':')))
            if not status['scheduler_active']:
                return
            uptime = time.monotonic()
            try:
                previous = float(LAST.read_text())
            except (OSError, ValueError):
                previous = None
            signature, changed, ready = dpkg_snapshot()
            if uptime < 60 or not ready or status['service_state'] in (1, 2, 3):
                return
            if not changed and previous is not None and uptime - previous < INTERVALS[settings['interval']]:
                return
            command('start', '--no-block', 'updates-monitor.service')
            atomic(LAST, str(uptime))
            if signature is not None:
                atomic(DPKG_SEEN, signature)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            print('Błąd harmonogramu:', exc, file=sys.stderr)
            atomic(HEALTH, json.dumps({'valid': 0, 'scheduler_active': 0, 'service_state': 0,
                                      'service_failed': 0, 'interval_seconds': 0,
                                      'updated_at': int(time.time()), 'reboot_required': 2, 'kernel_update_pending': 2, 'package_scan_current': 0}, separators=(',', ':')))
            raise SystemExit(1)


def main():
    args = sys.argv[1:]
    if args == ['reboot-status']:
        print(json.dumps({'reboot_required': reboot_required(), 'kernel_update_pending': kernel_update_pending(),
            'package_scan_current': package_scan_current()}))
    elif args == ['tick']:
        tick()
    elif args == ['init']:
        init()
    elif args == ['show']:
        data = load()
        data['cron_active'] = command('is-active', '--quiet', 'cron.service', check=False).returncode == 0
        print(json.dumps(data))
    elif len(args) == 2 and args[0] == 'enable' and args[1] in ('0', '1'):
        data = load()
        data['enabled'] = args[1] == '1'
        save(data)
        if data['enabled']:
            atomic(LAST, str(time.monotonic()))
    elif len(args) == 2 and args[0] == 'interval' and args[1] in INTERVALS:
        data = load()
        data['interval'] = args[1]
        save(data)
    else:
        raise SystemExit('Użycie: scheduler.py init|tick|show|enable 0/1|interval wartość')


if __name__ == '__main__':
    main()
