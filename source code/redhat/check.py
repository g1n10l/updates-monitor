#!/usr/bin/python3
"""Report DNF upgrade candidates and security advisories to Zabbix."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

VERSION = '0.5.17-2'
STATE = Path('/run/updates-monitor/state.json')
EMPTY = {'monitor_version': VERSION, 'regular': 0, 'security': 0, 'kernel_security': 0, 'valid': 0, 'checked_at': 0}
KERNEL = re.compile(r'^kernel(?:-|$)')
PACKAGE = re.compile(r'^[A-Za-z0-9_+.-]+\.[A-Za-z0-9_]+$')


def query(*args):
    result = subprocess.run(['/usr/bin/dnf', '-q', '--setopt=skip_if_unavailable=False', *args],
                            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, timeout=900, env=dict(os.environ, LC_ALL='C'))
    return result.stdout


def candidates(output):
    result = set()
    for line in output.splitlines():
        line = line.strip()
        if not PACKAGE.fullmatch(line):
            raise ValueError('Nieoczekiwany wynik DNF: ' + line)
        result.add(line)
    return result


def check():
    query('makecache', '--refresh')
    fmt = '%{name}.%{arch}'
    all_updates = candidates(query('repoquery', '--upgrades', '--latest-limit=1', '--qf', fmt))
    security = candidates(query('repoquery', '--upgrades', '--latest-limit=1', '--security', '--qf', fmt))
    security &= all_updates
    kernel = {p for p in all_updates if KERNEL.match(p.rsplit('.', 1)[0])}
    return {'monitor_version': VERSION, 'regular': len(all_updates - security - kernel), 'security': len(security - kernel),
                       'kernel_security': len(kernel), 'valid': 1, 'checked_at': int(time.time()),
                       'dist_upgrade_available': 2, 'dist_upgrade_current': '',
                       'dist_upgrade_target': '', 'dist_upgrade_error': 'Wykrywanie wydania dystrybucji obsługuje Debian i Ubuntu',
                       'dist_upgrade_checked_at': int(time.time())}


def write_state(value):
    STATE.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    if Path('/sys/fs/selinux/enforce').exists():
        subprocess.run(['/usr/sbin/restorecon', str(STATE.parent)], check=True)
    fd, tmp = tempfile.mkstemp(prefix='.state-', dir=STATE.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(value, output, separators=(',', ':'))
            output.write('\n')
        os.chmod(tmp, 0o644)
        os.replace(tmp, STATE)
        if Path('/sys/fs/selinux/enforce').exists():
            subprocess.run(['/usr/sbin/restorecon', str(STATE)], check=True)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


if __name__ == '__main__':
    try:
        result = check()
    except Exception as exc:
        print('Błąd kontroli aktualizacji:', exc, file=sys.stderr)
        try:
            result = json.loads(STATE.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            result = dict(EMPTY)
        result['monitor_version'] = VERSION
        result['valid'] = 0
        write_state(result)
        sys.exit(1)
    write_state(result)
    print(json.dumps(result, ensure_ascii=False))
