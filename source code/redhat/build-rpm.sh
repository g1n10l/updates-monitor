#!/bin/bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
output="$root/../install"
command -v rpmbuild >/dev/null || { echo 'Zainstaluj rpm-build i uruchom na RHEL 8/9 lub zgodnym systemie.' >&2; exit 1; }
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
if [[ $(uname -s) == Darwin ]] && command -v brew >/dev/null && command -v ginstall >/dev/null; then
    export PATH="$(brew --prefix coreutils)/libexec/gnubin:$PATH"
fi
mkdir -p "$work"/{BUILD,RPMS,SOURCES,SPECS,SRPMS,payload} "$output"
cp "$root/redhat/check.py" "$work/payload/check.py"
sed -e 's/cron\.service/crond.service/g' -e 's/text=True/universal_newlines=True/g' "$root/updates-monitor-scheduler.py" > "$work/payload/scheduler.py"
sed -e 's|/usr/local/lib/updates-monitor/|/usr/libexec/updates-monitor/|g' -e 's/cron\.service/crond.service/g' "$root/updates-monitor" > "$work/payload/updates-monitor"
for f in updates-monitor.service updates-monitor-scheduler.service; do
    sed 's|/usr/local/lib/updates-monitor/|/usr/libexec/updates-monitor/|g' "$root/$f" > "$work/payload/$f"
done
cp "$root/updates-monitor.cron" "$root/install-message.sh" "$root/zabbix-updates-monitor.json" "$root/zabbix-updates-monitor-correlation.json" "$root/setup-zabbix-correlation.py" "$work/payload/"
cp "$root/debian/agent.conf" "$work/payload/agent.conf"
cp "$root/redhat/README.txt" "$work/payload/README.txt"
cp "$root/redhat/updates-monitor.8" "$work/payload/updates-monitor.8"
tar -C "$work/payload" -czf "$work/SOURCES/updates-monitor-rpm.tar.gz" .
rpmbuild --define "_topdir $work" --define "_tmppath $work" --define '_prefix /usr' --define '_sysconfdir /etc' --define '_unitdir /usr/lib/systemd/system' --define '_rpmformat 4' --define '_binary_payload w9.gzdio' --define 'dist %{nil}' --target noarch-linux -bb "$root/redhat/updates-monitor.spec"
cp "$work/RPMS/noarch/updates-monitor-0.5.17-2.noarch.rpm" "$output/"
