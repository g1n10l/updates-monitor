#!/usr/bin/env python3
"""Buduje samorozpakowujący się instalator Debian/Ubuntu bez zależności PyPI."""
import base64
import gzip
import hashlib
import io
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent
FILES = ('install.sh', 'install-message.sh', 'updates-monitor', 'updates-monitor.py', 'updates-monitor.8',
         'updates-monitor.service', 'updates-monitor-scheduler.py', 'updates-monitor-scheduler.service',
         'updates-monitor.cron', 'zabbix-updates-monitor.json', 'zabbix-updates-monitor-correlation.json',
         'setup-zabbix-correlation.py', 'README.txt')
HEADER = r'''#!/bin/bash
set -euo pipefail
usage() {
    printf '%s\n' 'Użycie: sudo bash updates-monitor-installer.run' \
        '       bash updates-monitor-installer.run --check' \
        '       bash updates-monitor-installer.run --extract NOWY_KATALOG'
}
case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    --check) [[ $# == 1 ]] || { usage >&2; exit 2; } ;;
    --extract) [[ $# == 2 ]] || { usage >&2; exit 2; } ;;
    '') [[ $# == 0 ]] || { usage >&2; exit 2; }
        [[ $EUID == 0 ]] || { echo 'Uruchom instalator przez sudo.' >&2; exit 1; } ;;
    *) usage >&2; exit 2 ;;
esac
work=$(mktemp -d "${TMPDIR:-/tmp}/updates-monitor-installer.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
awk '/^__UPDATES_MONITOR_ARCHIVE__$/ {found=1; next} found {print}' "$0" | base64 -d > "$work/payload.tar.gz"
if [[ ${1:-} == --check ]]; then
    tar -tzf "$work/payload.tar.gz" >/dev/null
    echo 'Archiwum instalatora jest poprawne.'
    exit 0
fi
if [[ ${1:-} == --extract ]]; then
    [[ ! -e $2 ]] || { echo 'Katalog docelowy już istnieje.' >&2; exit 1; }
    mkdir -p -- "$2"
    tar -xzf "$work/payload.tar.gz" -C "$2" --no-same-owner
    echo "Rozpakowano pliki do: $2"
    exit 0
fi
tar -xzf "$work/payload.tar.gz" -C "$work" --no-same-owner
bash "$work/install.sh"
exit 0
__UPDATES_MONITOR_ARCHIVE__
'''


def build():
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode='wb', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            for name in FILES:
                path = ROOT / name
                data = path.read_bytes()
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o755 if name in ('install.sh', 'updates-monitor', 'updates-monitor.py', 'updates-monitor-scheduler.py') else 0o644
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                archive.addfile(info, io.BytesIO(data))
    out = ROOT.parent / 'install' / 'updates-monitor-installer.run'
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(HEADER.encode('utf-8') + base64.encodebytes(buffer.getvalue()))
    out.chmod(0o755)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    (out.parent / 'SHA256SUMS').write_text(f'{digest}  {out.name}\n', encoding='ascii')
    print(f'Instalator: {out}\nSHA-256: {digest}')


if __name__ == '__main__':
    build()
