#!/usr/bin/env python3
"""Build a Debian binary package using the Python standard library."""
import gzip
import hashlib
import io
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent
PACKAGE = 'updates-monitor_0.5.17-2_all.deb'


def compressed(data):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', mtime=0) as stream:
        stream.write(data)
    return buf.getvalue()


def tar_bytes(files):
    buf = io.BytesIO()
    dirs = set()
    for name in files:
        parent = Path(name).parent
        while str(parent) != '.':
            dirs.add(parent.as_posix())
            parent = parent.parent
    with tarfile.open(fileobj=buf, mode='w', format=tarfile.GNU_FORMAT) as tar:
        for name in sorted(dirs, key=lambda d: (d.count('/'), d)):
            info = tarfile.TarInfo('./' + name)
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            info.mtime = 0
            info.uid = info.gid = 0
            tar.addfile(info)
        for name, (content, mode) in files.items():
            info = tarfile.TarInfo('./' + name)
            info.mode = mode
            info.uid = info.gid = 0
            info.mtime = 0
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return compressed(buf.getvalue())


def member(name, data):
    header = (f'{name + "/":<16}{0:<12}{0:<6}{0:<6}{"100644":<8}{len(data):<10}`\n').encode('ascii')
    if len(header) != 60:
        raise ValueError('Invalid ar header')
    return header + data + (b'\n' if len(data) % 2 else b'')


def build():
    read = lambda name: (ROOT / name).read_bytes()
    service = read('updates-monitor.service').replace(b'/usr/local/lib/updates-monitor/', b'/usr/lib/updates-monitor/')
    scheduler_service = read('updates-monitor-scheduler.service').replace(b'/usr/local/lib/updates-monitor/', b'/usr/lib/updates-monitor/')
    files = {
        'usr/sbin/updates-monitor': (read('updates-monitor').replace(b'/usr/local/lib/updates-monitor/', b'/usr/lib/updates-monitor/'), 0o755),
        'usr/lib/updates-monitor/check.py': (read('updates-monitor.py'), 0o755),
        'usr/lib/updates-monitor/scheduler.py': (read('updates-monitor-scheduler.py'), 0o755),
        'usr/lib/updates-monitor/install-message.sh': (read('install-message.sh'), 0o644),
        'lib/systemd/system/updates-monitor.service': (service, 0o644),
        'lib/systemd/system/updates-monitor-scheduler.service': (scheduler_service, 0o644),
        'etc/cron.d/updates-monitor': (read('updates-monitor.cron'), 0o644),
        'usr/share/man/man8/updates-monitor.8.gz': (compressed(read('updates-monitor.8')), 0o644),
        'usr/share/updates-monitor/zabbix-updates-monitor.json': (read('zabbix-updates-monitor.json'), 0o644),
        'usr/share/updates-monitor/setup-zabbix-correlation.py': (read('setup-zabbix-correlation.py'), 0o755),
        'usr/share/updates-monitor/zabbix-updates-monitor-correlation.json': (read('zabbix-updates-monitor-correlation.json'), 0o644),
        'usr/share/updates-monitor/agent.conf': (read('debian/agent.conf'), 0o644),
        'usr/share/doc/updates-monitor/README.txt': (read('README.txt'), 0o644),
        'etc/zabbix/updates-monitor/agent.conf': (read('debian/agent.conf'), 0o644),
    }
    control = {'control': (read('debian/control'), 0o644),
               'conffiles': (b'/etc/zabbix/updates-monitor/agent.conf\n', 0o644)}
    for name in ('preinst', 'postinst', 'prerm', 'postrm'):
        control[name] = (read('debian/' + name), 0o755)
    package = b'!<arch>\n' + member('debian-binary', b'2.0\n')
    package += member('control.tar.gz', tar_bytes(control))
    package += member('data.tar.gz', tar_bytes(files))
    out = ROOT.parent / 'install' / PACKAGE
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(package)
    sha = hashlib.sha256(package).hexdigest()
    (out.parent / (PACKAGE + '.sha256')).write_text(f'{sha}  {PACKAGE}\n', encoding='ascii')
    for name in ('install-deb.sh',):
        target = out.parent / name
        target.write_bytes(read(name))
        target.chmod(0o755)
    bundle = out.parent / 'updates-monitor-deb-installer.tar.gz'
    bundle.write_bytes(tar_bytes({PACKAGE: (package, 0o644),
                                  'install-deb.sh': (read('install-deb.sh'), 0o755),
                                  PACKAGE + '.sha256': ((f'{sha}  {PACKAGE}\n').encode('ascii'), 0o644)}))
    versioned_bundle = out.parent / 'updates-monitor-0.5.17-2-deb-installer.tar.gz'
    versioned_bundle.write_bytes(bundle.read_bytes())
    bundle_hash = hashlib.sha256(bundle.read_bytes()).hexdigest()
    (out.parent / (bundle.name + '.sha256')).write_text(f'{bundle_hash}  {bundle.name}\n', encoding='ascii')
    (versioned_bundle.parent / (versioned_bundle.name + '.sha256')).write_text(
        f'{bundle_hash}  {versioned_bundle.name}\n', encoding='ascii')
    print(f'Pakiet: {out}\nSHA-256: {sha}')


if __name__ == '__main__':
    build()
