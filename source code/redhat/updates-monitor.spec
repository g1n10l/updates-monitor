Name:           updates-monitor
Version:        0.5.13
Release:        1%{?dist}
Summary:        Monitor DNF updates for Zabbix
License:        Proprietary
URL:            https://github.com/g1n10l/updates-monitor
BuildArch:      noarch
Source0:        updates-monitor-rpm.tar.gz
Requires:       python3, dnf, dnf-plugins-core, cronie, systemd, util-linux, policycoreutils, policycoreutils-python-utils

%description
Monitor cumulative regular, security and kernel update checks using DNF.

%prep
%setup -q -c -T
%{__tar} -xf %{SOURCE0}

%install
install -Dm755 updates-monitor %{buildroot}%{_sbindir}/updates-monitor
install -Dm755 check.py %{buildroot}%{_libexecdir}/updates-monitor/check.py
install -Dm755 scheduler.py %{buildroot}%{_libexecdir}/updates-monitor/scheduler.py
install -Dm644 install-message.sh %{buildroot}%{_libexecdir}/updates-monitor/install-message.sh
install -Dm644 updates-monitor.service %{buildroot}%{_unitdir}/updates-monitor.service
install -Dm644 updates-monitor-scheduler.service %{buildroot}%{_unitdir}/updates-monitor-scheduler.service
install -Dm644 updates-monitor.cron %{buildroot}%{_sysconfdir}/cron.d/updates-monitor
install -Dm644 agent.conf %{buildroot}%{_sysconfdir}/zabbix/updates-monitor/agent.conf
install -Dm644 agent.conf %{buildroot}%{_datadir}/updates-monitor/agent.conf
install -Dm644 updates-monitor.8 %{buildroot}%{_mandir}/man8/updates-monitor.8
install -Dm644 zabbix-updates-monitor.json %{buildroot}%{_datadir}/updates-monitor/zabbix-updates-monitor.json
install -Dm644 README.txt %{buildroot}%{_docdir}/updates-monitor/README-redhat.txt

%post
if [ ! -e /etc/zabbix/updates-monitor/agent.conf ]; then
    install -Dm644 %{_datadir}/updates-monitor/agent.conf /etc/zabbix/updates-monitor/agent.conf
fi
%{_libexecdir}/updates-monitor/scheduler.py init
if [ -e /sys/fs/selinux/enforce ] && { [ -f /etc/zabbix/zabbix_agentd.conf ] || [ -f /etc/zabbix/zabbix_agent2.conf ]; }; then
    if semanage fcontext -l -C | grep -F '/run/updates-monitor(/.*)?' >/dev/null; then
        semanage fcontext -m -t zabbix_runtime_t '/run/updates-monitor(/.*)?' || exit 1
    else
        semanage fcontext -a -t zabbix_runtime_t '/run/updates-monitor(/.*)?' || exit 1
    fi
    [ ! -d /run/updates-monitor ] || restorecon -RF /run/updates-monitor
fi
for config in /etc/zabbix/zabbix_agentd.conf /etc/zabbix/zabbix_agent2.conf; do
    [ -f "$config" ] || continue
    grep -Fx 'Include=/etc/zabbix/updates-monitor/agent.conf' "$config" >/dev/null || printf '\nInclude=/etc/zabbix/updates-monitor/agent.conf\n' >> "$config"
    [ ! -e /sys/fs/selinux/enforce ] || restorecon "$config"
done
if [ -d /run/systemd/system ]; then
    systemctl daemon-reload
    systemctl enable --now crond.service
    for unit in zabbix-agent.service zabbix-agent2.service; do
        if systemctl is-active --quiet "$unit"; then systemctl restart "$unit"; fi
    done
fi
. %{_libexecdir}/updates-monitor/install-message.sh
updates_monitor_install_message

%preun
if [ "$1" -eq 0 ]; then
    if [ -d /run/systemd/system ]; then systemctl stop updates-monitor-scheduler.service updates-monitor.service || :; fi
    for config in /etc/zabbix/zabbix_agentd.conf /etc/zabbix/zabbix_agent2.conf; do
        [ -f "$config" ] || continue
        sed -i '\|^Include=/etc/zabbix/updates-monitor/agent.conf$|d' "$config"
        [ ! -e /sys/fs/selinux/enforce ] || restorecon "$config"
    done
    if [ -d /run/systemd/system ]; then
        for unit in zabbix-agent.service zabbix-agent2.service; do
            if systemctl is-active --quiet "$unit"; then systemctl restart "$unit"; fi
        done
    fi
fi

%postun
if [ "$1" -eq 0 ]; then
    if [ -e /sys/fs/selinux/enforce ] && semanage fcontext -l -C | grep -F '/run/updates-monitor(/.*)?' >/dev/null; then
        semanage fcontext -d '/run/updates-monitor(/.*)?' || :
    fi
    if [ -d /run/systemd/system ]; then systemctl daemon-reload || :; fi
fi

%files
%{_sbindir}/updates-monitor
%{_libexecdir}/updates-monitor/
%{_unitdir}/updates-monitor.service
%{_unitdir}/updates-monitor-scheduler.service
%config(noreplace) %{_sysconfdir}/cron.d/updates-monitor
%config(noreplace) %{_sysconfdir}/zabbix/updates-monitor/agent.conf
%{_mandir}/man8/updates-monitor.8*
%{_datadir}/updates-monitor/zabbix-updates-monitor.json
%{_datadir}/updates-monitor/agent.conf
%doc %{_docdir}/updates-monitor/README-redhat.txt
