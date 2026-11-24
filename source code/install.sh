#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
[[ $EUID == 0 ]] || { echo 'Uruchom: sudo bash install.sh' >&2; exit 1; }
cd "$(dirname "$(readlink -f "$0")")"
. /etc/os-release
case ${ID:-} in debian|ubuntu) ;; *) echo 'Obsługiwane są Debian i Ubuntu.' >&2; exit 1;; esac
command -v systemctl >/dev/null || { echo 'Wymagany jest systemd.' >&2; exit 1; }
configs=()
for c in /etc/zabbix/zabbix_agentd.conf /etc/zabbix/zabbix_agent2.conf; do [[ ! -f $c ]] || configs+=("$c"); done
if ((${#configs[@]} == 0)); then
    echo 'Nie znaleziono agenta Zabbix. Monitoring przez Zabbix nie będzie dostępny do czasu jego instalacji i konfiguracji.' >&2
fi
selinux_tools=0
if [[ -e /sys/fs/selinux/enforce ]]; then
    if command -v semanage >/dev/null && command -v restorecon >/dev/null; then
        selinux_tools=1
    elif [[ $(cat /sys/fs/selinux/enforce) == 1 ]]; then
        echo 'SELinux enforcing wymaga semanage i restorecon.' >&2
        exit 1
    else
        echo 'SELinux permissive bez narzędzi; pomijam konfigurację etykiet.' >&2
    fi
fi
missing=()
if ! /usr/bin/python3 -c 'import apt' 2>/dev/null; then missing+=(python3-apt); fi
if [[ $(dpkg-query -W -f='${db:Status-Status}' cron 2>/dev/null || true) != installed ]]; then missing+=(cron); fi
if ((${#missing[@]})); then
    apt-get -o APT::Update::Error-Mode=any update
    apt-get install -y "${missing[@]}"
fi
install -d -m 0755 /usr/local/lib/updates-monitor /etc/zabbix/updates-monitor
install -m 0755 updates-monitor.py /usr/local/lib/updates-monitor/check.py
install -m 0755 updates-monitor-scheduler.py /usr/local/lib/updates-monitor/scheduler.py
install -m 0755 updates-monitor /usr/local/sbin/updates-monitor
install -m 0644 updates-monitor.service updates-monitor-scheduler.service /etc/systemd/system/
install -m 0644 updates-monitor.cron /etc/cron.d/updates-monitor
/usr/local/lib/updates-monitor/scheduler.py init
for old_timer in updates-monitor.timer updates-monitor-health.timer; do
    systemctl disable --now "$old_timer" 2>/dev/null || true
done
rm -f /etc/systemd/system/updates-monitor.timer /etc/systemd/system/updates-monitor-health.timer /etc/systemd/system/updates-monitor-health.service /etc/systemd/system/updates-monitor.timer.d/interval.conf /usr/local/lib/updates-monitor/health.py
rmdir /etc/systemd/system/updates-monitor.timer.d 2>/dev/null || true
install -d -m 0755 /usr/local/share/man/man8
install -m 0644 updates-monitor.8 /usr/local/share/man/man8/updates-monitor.8
if [[ $selinux_tools == 1 ]]; then
    if ((${#configs[@]})); then
        if semanage fcontext -l -C | grep -F '/run/updates-monitor(/.*)?' >/dev/null; then
            semanage fcontext -m -t zabbix_runtime_t '/run/updates-monitor(/.*)?'
        else
            semanage fcontext -a -t zabbix_runtime_t '/run/updates-monitor(/.*)?'
        fi
    fi
    if [[ -d /run/updates-monitor ]]; then restorecon -RF /run/updates-monitor; fi
fi
cat > /etc/zabbix/updates-monitor/agent.conf <<'EOF'
UserParameter=updates.monitor.raw,if [ -r /run/updates-monitor/state.json ]; then IFS= read -r data < /run/updates-monitor/state.json; printf '%s\n' "$data"; else printf '%s\n' '{"regular":0,"security":0,"kernel_security":0,"valid":0,"checked_at":0}'; fi
UserParameter=updates.monitor.health,if [ -r /run/updates-monitor/health.json ]; then IFS= read -r data < /run/updates-monitor/health.json; printf '%s\n' "$data"; else printf '%s\n' '{"valid":0,"scheduler_active":0,"service_state":0,"service_failed":0,"interval_seconds":0,"updated_at":0}'; fi
EOF
chmod 0644 /etc/zabbix/updates-monitor/agent.conf
for c in "${configs[@]}"; do
    grep -Fx 'Include=/etc/zabbix/updates-monitor/agent.conf' "$c" >/dev/null || printf '\nInclude=/etc/zabbix/updates-monitor/agent.conf\n' >> "$c"
done
systemctl daemon-reload
systemctl enable --now cron.service
systemctl start --no-block updates-monitor-scheduler.service
for unit in zabbix-agent.service zabbix-agent2.service; do
    if systemctl is-active --quiet "$unit"; then systemctl restart "$unit"; fi
done
echo 'Zainstalowano. Uruchom pierwszą kontrolę: systemctl start updates-monitor.service'
. ./install-message.sh
updates_monitor_install_message
