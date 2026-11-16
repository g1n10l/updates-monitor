#!/usr/bin/python3
"""Sprawdza aktualizacje APT; nie instaluje pakietów."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

import apt

STATE = Path('/run/updates-monitor/state.json')
EMPTY = {'regular': 0, 'security': 0, 'kernel_security': 0, 'valid': 0, 'checked_at': 0}
COUNT_KEYS = ('regular', 'security', 'kernel_security')
KERNEL = re.compile(r'^linux-(image|headers|modules|modules-extra|signed-image|unsigned|tools|cloud-tools|kbuild|libc-dev|generic|virtual|aws|azure|gcp|kvm|oem|raspi|lowlatency|hwe)(-|$)')


def write_state(value):
    STATE.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    if Path('/sys/fs/selinux/enforce').exists():
        subprocess.run(['/usr/sbin/restorecon', str(STATE.parent)], check=True)
    fd, tmp = tempfile.mkstemp(prefix='.state-', dir=STATE.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(value, out, separators=(',', ':'))
            out.write('\n')
        os.chmod(tmp, 0o644)
        os.replace(tmp, STATE)
        if Path('/sys/fs/selinux/enforce').exists():
            subprocess.run(['/usr/sbin/restorecon', str(STATE)], check=True)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def accumulate(result):
    """Add this scan to the last result; clear a category when none remain."""
    try:
        previous = json.loads(STATE.read_text(encoding='utf-8'))
    except FileNotFoundError:
        previous = {}
    for key in COUNT_KEYS:
        old = previous.get(key, 0)
        if type(old) is not int or old < 0:
            raise ValueError('Nieprawidłowy poprzedni licznik: ' + key)
        result[key] = old + result[key] if result[key] else 0
    return result


def check():
    env = dict(os.environ, LC_ALL='C', DEBIAN_FRONTEND='noninteractive')
    subprocess.run(['apt-get', '-o', 'APT::Update::Error-Mode=any', '-o', 'Acquire::Retries=2', 'update'],
                   check=True, timeout=900, env=env)
    cache = apt.Cache()
    # Analiza full-upgrade obejmuje nowe pakiety kernela; nie instaluje ani nie usuwa pakietów.
    cache.upgrade(dist_upgrade=True)
    result = dict(EMPTY)
    for package in cache.get_changes():
        if package.candidate is None:
            continue
        security = any((origin.archive or '').lower().endswith('-security')
                       for origin in package.candidate.origins)
        kernel = bool(KERNEL.match(package.name))
        new_kernel = package.marked_install and not package.is_installed and kernel
        if not package.marked_upgrade and not new_kernel:
            continue
        # Keep the serialized key for compatibility with existing Zabbix items.
        group = 'kernel_security' if kernel else 'security' if security else 'regular'
        result[group] += 1
    result.update(valid=1, checked_at=int(time.time()))
    return accumulate(result)


if __name__ == '__main__':
    try:
        result = check()
    except Exception as exc:
        print('Błąd kontroli aktualizacji:', exc, file=sys.stderr)
        try:
            result = json.loads(STATE.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            result = dict(EMPTY)
        result['valid'] = 0
        write_state(result)
        sys.exit(1)
    write_state(result)
    print(json.dumps(result, ensure_ascii=False))
