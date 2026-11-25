#!/usr/bin/python3
"""Sprawdza aktualizacje APT; nie instaluje pakietów."""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

import apt

VERSION = '0.5.17-2'
STATE = Path('/run/updates-monitor/state.json')
EMPTY = {'monitor_version': VERSION, 'regular': 0, 'security': 0, 'kernel_security': 0, 'valid': 0, 'checked_at': 0}
KERNEL = re.compile(r'^linux-(image|headers|modules|modules-extra|signed-image|unsigned|tools|cloud-tools|kbuild|libc-dev|generic|virtual|aws|azure|gcp|kvm|oem|raspi|lowlatency|hwe)(-|$)')


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


def write_state(value):
    STATE.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    restore_context(STATE.parent)
    fd, tmp = tempfile.mkstemp(prefix='.state-', dir=STATE.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(value, out, separators=(',', ':'))
            out.write('\n')
        os.chmod(tmp, 0o644)
        os.replace(tmp, STATE)
        restore_context(STATE)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_os_release():
    values = {}
    for line in Path('/etc/os-release').read_text(encoding='utf-8').splitlines():
        if '=' not in line or line.startswith('#'):
            continue
        key, value = line.split('=', 1)
        words = shlex.split(value)
        values[key] = words[0] if len(words) == 1 else ''
    return values


def debian_release(suite):
    url = 'https://deb.debian.org/debian/dists/' + suite + '/Release'
    with urllib.request.urlopen(url, timeout=15) as response:
        header = response.read(65536).decode('utf-8')
    values = dict(line.split(': ', 1) for line in header.splitlines() if ': ' in line)
    if values.get('Origin') != 'Debian' or values.get('Suite') != suite:
        raise ValueError('Nieprawidłowe metadane wydania Debiana')
    version = values.get('Version', '')
    if not re.fullmatch(r'[0-9]+(?:[.][0-9]+)*', version):
        raise ValueError('Brak numeru stabilnego wydania Debiana')
    codename = values.get('Codename', '')
    if not re.fullmatch(r'[a-z]+', codename):
        raise ValueError('Brak nazwy wydania Debiana')
    return int(version.split('.')[0]), codename


def distribution_status():
    # Unknown is separate from "no upgrade" and never closes an existing alert.
    result = {'dist_upgrade_available': 2, 'dist_upgrade_current': '',
              'dist_upgrade_target': '', 'dist_upgrade_error': '',
              'dist_upgrade_checked_at': int(time.time())}
    try:
        release = read_os_release()
        distro = release.get('ID', '')
        current = release.get('VERSION_ID', '')
        result['dist_upgrade_current'] = release.get('PRETTY_NAME', '') or distro + ' ' + current
        if distro == 'debian':
            if not re.fullmatch(r'[0-9]+(?:[.][0-9]+)*', current):
                raise ValueError('Nieznana wersja Debiana')
            installed = int(current.split('.')[0])
            latest, codename = debian_release('stable')
            if latest <= installed:
                result['dist_upgrade_available'] = 0
            else:
                target = latest
                if latest != installed + 1:
                    target, codename = debian_release('oldstable')
                if target != installed + 1:
                    raise ValueError('Brak potwierdzonej ścieżki do następnego wydania Debiana')
                result.update(dist_upgrade_available=1,
                              dist_upgrade_target='Debian ' + str(target) + ' (' + codename + ')')
        elif distro == 'ubuntu':
            tool = shutil.which('do-release-upgrade')
            if not tool:
                raise ValueError('Brak do-release-upgrade z pakietu ubuntu-release-upgrader-core')
            check = subprocess.run([tool, '-c'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   universal_newlines=True, timeout=90,
                                   env=dict(os.environ, LC_ALL='C', LANGUAGE='C'))
            output = check.stdout + '\n' + check.stderr
            match = re.search(r"New release '([^'\r\n]+)' available", output)
            if check.returncode == 0 and match:
                result.update(dist_upgrade_available=1, dist_upgrade_target='Ubuntu ' + match.group(1))
            elif check.returncode in (0, 1) and re.search(r'^No new release found[.]?$', output, re.M) and not check.stderr.strip() and not re.search(r'failed|error|unable', output, re.I):
                result['dist_upgrade_available'] = 0
            else:
                raise ValueError('Nie można potwierdzić dostępności wydania Ubuntu: ' + output.strip()[:300])
        else:
            raise ValueError('Wykrywanie aktualizacji dystrybucji obsługuje Debian i Ubuntu')
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result['dist_upgrade_error'] = str(exc)[:400]
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
        if not (package.marked_upgrade or package.marked_install or
                getattr(package, 'marked_downgrade', False)):
            continue
        # Keep the serialized key for compatibility with existing Zabbix items.
        group = 'kernel_security' if kernel else 'security' if security else 'regular'
        result[group] += 1
    result.update(distribution_status())
    result.update(valid=1, checked_at=int(time.time()))
    return result


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
