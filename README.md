# updates-monitor

`updates-monitor` checks for available system updates and sends cumulative scan counts to Zabbix. It does not install or remove packages.

## What it monitors

The results are split into three categories:

| Category | Zabbix alert |
| --- | --- |
| Regular updates | Blue alert showing the cumulative count |
| Security updates | Yellow alert showing the cumulative count |
| Kernel updates | Red alert showing the cumulative count |

**Restart notification:** Zabbix shows a warning naming the host when it requires a restart and a successful update check reports `0` regular, security, and kernel updates. See [Restart required after updates](#restart-required-after-updates) for the detection and recovery rules.

**Kernel update notification:** A newer kernel image also triggers the single `Wymagany restart hosta` warning once a valid check confirms zero pending updates. See [New kernel restart recommendation](#new-kernel-restart-recommendation).

Zabbix also receives the time of the last check, the schedule status, and the service status. The public [Zabbix template](template/updates-monitor.json) is included in the installation package at `/usr/share/updates-monitor/zabbix-updates-monitor.json`. The installer configures an existing Zabbix agent or agent 2 to read the results. Install and configure the agent separately.

## Restart required after updates

The scheduler reports reboot status in `updates.monitor.reboot_required` through the existing health item. Zabbix raises a warning containing the host name when a restart is required and a valid scan shows zero regular, security and kernel updates. It closes the warning only after both reboot sources confirm no restart is needed and a valid scan exists; unknown data do not confirm recovery. The status is refreshed on each scheduler tick, normally once per minute, independently of the update scan interval. The agent and Zabbix polling add delay.

On Debian and Ubuntu the check uses `/run/reboot-required`, which only reflects packages that create the marker. On RHEL-compatible systems it runs `dnf needs-restarting -r` from `dnf-plugins-core` as the scheduler user. A missing tool, unrecognized result, failed check or old agent reports status 2 (unknown), not a clear result. Monitoring covers host reboots; individual services may also require a restart. The alert does not restart a host.

Update the installed monitor on each host and import the updated template. A template imported before the new monitor reports an unknown reboot status until the host is upgraded. Existing agent keys are unchanged.

## New kernel restart recommendation

The Zabbix item `updates.monitor.kernel_update_pending` compares the running kernel version with kernel images of the same flavour or architecture in `/boot`. A newer image yields 1; no newer image yields 0; an unsupported version format, missing images or comparison error yields 2 (unknown). The combined warning names the host when either this value or the system reboot indicator is 1, a valid scan after the latest package database change shows all three categories at zero, and the check service is idle. Both restart sources must report 0 before the warning closes; unknown data do not close it.

This is a recommendation based on files in `/boot`, not proof that the bootloader is configured to load the newer image. Retained or manually installed images can influence the result. It is independent of the system reboot-required marker; both sources feed one warning. A separate boot partition must be mounted for the check. The scheduler refreshes the result on each tick, normally once per minute.

## When checks run

- The default interval is **one day**. Available values are `2h`, `6h`, `12h`, `1D`, `5D`, `10D`, `15D`, and `30D`.
- Cron checks the schedule every minute. The first check is scheduled about one minute after boot.
- On Debian and Ubuntu, a change to the dpkg package database schedules another check after the package manager releases its locks. Installing updates can therefore change the counts without a reboot, usually within a minute.
- After a reboot, the counts start at zero and the result remains marked invalid until the first successful check. After an error, the previous counts are retained but marked invalid.

Each successful check counts the current upgrade candidates in all three categories and adds the full count to the previous result. For example, 3 followed by 5 becomes 8. A category resets to 0 when a successful check finds no candidates in it. Repeated checks of the same pending packages increase the cumulative count again; it is not a count of unique packages or the number currently waiting to be installed.

Checks use package repository metadata. Timely results require repository access and a running cron service.

## Installation

### Debian and Ubuntu

Download the [DEB package, version 0.5.13-1](install/updates-monitor_0.5.13-1_all.deb). The downloaded file must be a DEB package, not a GitHub HTML page.

```sh
curl -fL -o updates-monitor.deb https://raw.githubusercontent.com/g1n10l/updates-monitor/main/install/updates-monitor_0.5.13-1_all.deb
echo '98b54ba8cdee04d80c1880ff8d7c523c6805828eae8953f338df58f7177ded2d  updates-monitor.deb' | sha256sum -c -
sudo dpkg -i updates-monitor.deb
```

The package depends on `python3`, `python3-apt`, `apt`, `systemd`, `util-linux`, and `cron`. If `dpkg` reports missing dependencies, run `sudo apt --fix-broken install`.

The RUN installer can be built from [source](source%20code/build-installer.py). It installs into `/usr/local` and does not provide a package manager uninstall command.

To remove the package and its configuration:

```sh
sudo apt purge updates-monitor
```

### Red Hat family

The [RPM package, version 0.5.13-1](install/updates-monitor-0.5.13-1.noarch.rpm), is experimental. It has not been verified on a running RHEL system and is unsigned.

```sh
curl -fL -o updates-monitor-0.5.13-1.noarch.rpm https://raw.githubusercontent.com/g1n10l/updates-monitor/main/install/updates-monitor-0.5.13-1.noarch.rpm
echo '14cf69934586d742f9d3a6990dd28a863685526089597b7742b5111414b1302b  updates-monitor-0.5.13-1.noarch.rpm' | sha256sum -c -
sudo dnf install updates-monitor-0.5.13-1.noarch.rpm
```

To remove it, run `sudo dnf remove updates-monitor`. Configuration and schedule files may remain after removing the RPM.

## Usage

```sh
sudo updates-monitor status        # Run a check and display the results
sudo updates-monitor interval 0    # Disable automatic checks
sudo updates-monitor interval 2h   # Check every 2 hours
sudo updates-monitor interval 6h   # Check every 6 hours
sudo updates-monitor interval 12h  # Check every 12 hours
sudo updates-monitor interval 1D   # Check every day
sudo updates-monitor interval 5D   # Check every 5 days
sudo updates-monitor interval 10D  # Check every 10 days
sudo updates-monitor interval 15D  # Check every 15 days
sudo updates-monitor interval 30D  # Check every 30 days
man updates-monitor                # Show the manual
```

Setting any nonzero interval enables automatic checks. `interval 0` disables them, but a manual `status` command still runs a check. A disabled schedule is reported in Zabbix. Package changes on Debian and Ubuntu can also trigger a check when automatic checks are enabled.

`status` displays cumulative scan counts, the last successful check, restart status, the interval, and service status. The service performs one check and may show as `inactive` after it finishes. If a check fails, `status` also shows recent errors from `journalctl`.

Check the installed version and view service details with:

```sh
dpkg-query -W updates-monitor                         # Debian and Ubuntu
rpm -q updates-monitor                                # RHEL-compatible systems
systemctl status updates-monitor.service --no-pager   # Check service state
journalctl -u updates-monitor.service -n 50 --no-pager # Read recent service logs
```

## Zabbix and files

Import the [template](template/updates-monitor.json) or `/usr/share/updates-monitor/zabbix-updates-monitor.json` into Zabbix, then link `updates-monitor` to the host. Set `Server` and, if using active checks, `ServerActive` in the agent configuration.

| Path | Purpose |
| --- | --- |
| `/etc/cron.d/updates-monitor` | Cron jobs |
| `/etc/updates-monitor/schedule.json` | Schedule status and interval |
| `/etc/zabbix/updates-monitor/agent.conf` | Zabbix agent keys |
| `/run/updates-monitor/state.json` | Package counts and result validity |
| `/run/updates-monitor/health.json` | Service and schedule status |

## Counting limits

On Debian and Ubuntu, the script identifies security archives by the `-security` suffix and examines a `full-upgrade` plan. All kernel upgrades and new kernel packages are counted in the kernel category, regardless of source. Custom repositories and some Ubuntu ESM updates may be counted as regular updates. Some other new dependencies and held packages may be omitted.

For the RPM version, security classification depends on DNF repository `updateinfo` metadata. Each check counts package candidates; the cumulative totals count repeated observations of the same packages and do not represent vulnerabilities.

Created by **G1n10L**.


## Source code and builds

The complete source code, package definitions and tests are in
[`source code/`](source%20code/). Ready-built packages remain in
[`install/`](install/), and the published Zabbix template is in
[`template/`](template/).

```text
updates-monitor/
├── source code/        # Source code, documentation, packaging and tests
├── install/            # DEB and RPM packages
└── template/           # Published Zabbix template
```

From the repository root, build packages with:

```sh
python3 "source code/build-deb.py"
python3 "source code/build-installer.py"
bash "source code/redhat/build-rpm.sh"
```

The RPM build requires the tools described in the
[RPM build notes](source%20code/redhat/README.txt). Generated files go to
`install/`. The [source manual](source%20code/README.md) and
[Polish instructions](source%20code/README.txt) describe operation and packaging.

Run the isolated checks with:

```sh
for test in "source code"/tests/test_*.py; do
    python3 "$test" || exit 1
done
```
