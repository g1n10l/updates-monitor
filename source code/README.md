# updates-monitor

This is the source directory. Commands below assume this working directory;
ready-built installers are in [`../install/`](../install/).

Monitor Linux package updates with Zabbix. The tool reports cumulative scan counts in three separate categories: regular updates, security updates, and all kernel updates. It refreshes repository metadata but does not install or remove updates.

## Platforms and packages

- **Debian and Ubuntu:** APT, systemd and cron. Install the [DEB package](../install/updates-monitor_0.5.12-1_all.deb). The optional RUN installer can be built with [build-installer.py](build-installer.py).
- **RHEL 8/9 and compatible systems:** an [RPM package](../install/updates-monitor-0.5.12-1.noarch.rpm) using DNF 4 and crond is provided as an experimental build. Its classification has been tested with simulated data, but installation and operation on a live RHEL system have not yet been verified. The RPM is unsigned. See the [Red Hat build notes](redhat/README.txt).

The installers do not install a Zabbix agent or add a Zabbix repository. They configure an existing Zabbix agent or agent 2; set `Server` and, if applicable, `ServerActive` in the agent configuration separately. The RUN installer does not currently include an uninstaller.

## Install and remove

### Debian family

On Debian, Ubuntu and compatible systems, install the downloaded DEB package:

```sh
curl -fL -o updates-monitor.deb https://raw.githubusercontent.com/g1n10l/updates-monitor/main/install/updates-monitor_0.5.12-1_all.deb
echo '4ae76174fb4883521260d170f5ac189321da229e54930d5b271bcbd15b526cee  updates-monitor.deb' | sha256sum -c -
sudo dpkg -i updates-monitor.deb
```

The download link points directly to the DEB file in the public repository. Proceed with installation only if the checksum reports `OK`. If `dpkg` reports missing dependencies, install them with `sudo apt --fix-broken install`.

To uninstall the DEB package and remove its saved schedule:

```sh
sudo apt purge updates-monitor
```

After building the optional RUN installer, install using `sudo bash ../install/updates-monitor-installer.run`. This RUN installer does not include an uninstaller.

### Red Hat family

On RHEL 8/9 and compatible systems, install the experimental RPM package:

```sh
sudo dnf install updates-monitor-0.5.12-1.noarch.rpm
```

To uninstall it:

```sh
sudo dnf remove updates-monitor
```

RPM removal can leave configuration and schedule data on disk. This RPM has not yet been tested on a live RHEL system and is unsigned.

## Use

```sh
sudo updates-monitor status
sudo updates-monitor interval 6h
sudo updates-monitor interval 1D
sudo updates-monitor interval 30D
journalctl -u updates-monitor.service -n 50 --no-pager
```

Check the installed version with `dpkg-query -W updates-monitor` on Debian/Ubuntu or `rpm -q updates-monitor` on RHEL. `sudo updates-monitor interval 0` disables automatic scans; setting an interval re-enables them. Manual `status` still runs a scan.

Supported intervals are `2h`, `6h`, `12h`, `1D`, `5D`, `10D`, `15D` and `30D`. A new installation defaults to one day. Cron checks the schedule once a minute; a check is scheduled approximately one minute after boot and thereafter at the chosen interval. Checks can be delayed if the network or cron is unavailable. `status` starts a check and displays its results and service status.

On Debian and Ubuntu, the scheduler also detects changes to the dpkg package database. Once package manager locks are released, it schedules an additional check, usually within a minute, without a reboot. Changes include package installation, removal and configuration. If a check is already running, the additional check waits for it to finish.

Each successful check counts the current upgrade candidates in every category, then adds that count to the stored value. If the previous regular count was 3 and the next check sees 5 regular candidates, the stored count becomes 8. A category resets to 0 when a successful check finds no candidates in it. Repeated checks of the same pending packages increase the count again; these figures are cumulative scan totals, not unique packages or the number currently pending. A reboot clears the counters because they are stored in `/run`.

The schedule is stored in `/etc/updates-monitor/schedule.json`. Results and health are in `/run/updates-monitor/state.json` and `/run/updates-monitor/health.json`; they are recreated after reboot. A result with `valid: 0` does not confirm that there are no updates. Existing schedule settings are preserved or migrated during an upgrade; see [README.txt](README.txt) for details.

## Zabbix

Import [zabbix-updates-monitor.json](zabbix-updates-monitor.json) into Zabbix 7.4 and link the template **updates-monitor** to the host. The template uses the same agent keys for the experimental RPM variant. The template includes one item and trigger for each package category, plus health and freshness alerts. The event name shows the cumulative count at the time of the event; enable operational data in the Problems widget to see the latest cumulative count.

The installer adds `Include=/etc/zabbix/updates-monitor/agent.conf` to each detected agent configuration. Reinstalling the DEB or RPM restores a missing `agent.conf` without replacing an existing one. To test a configured agent locally:

```sh
zabbix_agentd -t updates.monitor.raw
zabbix_agentd -t updates.monitor.health
```

Use `zabbix_agent2` instead when running agent 2. No agent is installed automatically.

## Classification limits

On Debian and Ubuntu, APT security archives are identified by the `-security` suffix. Some custom sources and Ubuntu ESM updates may be classified as regular updates. The check models `full-upgrade`, counts all kernel upgrades and new kernel packages, and may omit other new dependencies, removals and held packages. The internal `kernel_security` key remains for compatibility with existing Zabbix items.

On RHEL-compatible systems, the DNF variant reports upgrade candidates rather than a resolved transaction. Security classification depends on repository `updateinfo` metadata; without it, security updates can be classified as regular. Kernel candidates are counted in the kernel category regardless of security metadata. Each check counts package candidates, then adds that count to the running total; the total is not a count of unique packages or vulnerabilities.

## Documentation and author

The manual is available after installation with `man updates-monitor`. More detailed Polish instructions are in [README.txt](README.txt). Created by **G1n10L**.

## Restart required after updates

The scheduler reports reboot status in `updates.monitor.reboot_required` through the existing health item. Zabbix raises a warning containing the host name when a restart is required and a valid scan shows zero regular, security and kernel updates. It closes the warning only after both reboot sources confirm no restart is needed and a valid scan exists; unknown data do not confirm recovery. The status is refreshed on each scheduler tick, normally once per minute, independently of the update scan interval. The agent and Zabbix polling add delay.

On Debian and Ubuntu the check uses `/run/reboot-required`, which only reflects packages that create the marker. On RHEL-compatible systems it runs `dnf needs-restarting -r` from `dnf-plugins-core` as the scheduler user. A missing tool, unrecognized result, failed check or old agent reports status 2 (unknown), not a clear result. Monitoring covers host reboots; individual services may also require a restart. The alert does not restart a host.

Update the installed monitor on each host and import the updated template. A template imported before the new monitor reports an unknown reboot status until the host is upgraded. Existing agent keys are unchanged.

## New kernel restart recommendation

The Zabbix item `updates.monitor.kernel_update_pending` compares the running kernel version with kernel images of the same flavour or architecture in `/boot`. A newer image yields 1; no newer image yields 0; an unsupported version format, missing images or comparison error yields 2 (unknown). The combined warning names the host when either this value or the system reboot indicator is 1, a valid scan after the latest package database change shows all three categories at zero, and the check service is idle. Both restart sources must report 0 before the warning closes; unknown data do not close it.

This is a recommendation based on files in `/boot`, not proof that the bootloader is configured to load the newer image. Retained or manually installed images can influence the result. It is independent of the system reboot-required marker; both sources feed one warning. A separate boot partition must be mounted for the check. The scheduler refreshes the result on each tick, normally once per minute.
