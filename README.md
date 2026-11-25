# updates-monitor

`updates-monitor` checks for available system updates and sends current pending package counts to Zabbix. It does not install or remove packages.

## What it monitors

The results are split into three categories:

| Category | Zabbix alert |
| --- | --- |
| Regular updates | Blue alert showing the current count |
| Security updates | Yellow alert showing the current count |
| Kernel updates | Red alert showing the current count |

**Restart notification:** Zabbix shows a warning naming the host when it requires a restart and a successful update check reports `0` regular, security, and kernel updates. See [Restart required after updates](#restart-required-after-updates) for the detection and recovery rules.

**Kernel update notification:** A newer kernel image also triggers the single `Wymagany restart hosta` warning once a valid check confirms zero pending updates. See [New kernel restart recommendation](#new-kernel-restart-recommendation).

Zabbix also receives the time of the last check, the schedule status, and the service status. The [Zabbix template](template/updates-monitor.json) is included in the installation package at `/usr/share/updates-monitor/zabbix-updates-monitor.json`. The installer configures an existing Zabbix agent or agent 2 to read the results. Install and configure the agent separately.

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

Each successful check counts the packages currently waiting to be installed. Five waiting packages plus three new ones means eight; checking those same eight again still reports eight. Installed packages disappear from the count. The total is the sum of the three disjoint categories. Debian includes upgrades and all new dependencies in the APT full-upgrade plan, matching `apt-get -s dist-upgrade` with the same metadata and configuration. Failed checks retain the last counts and mark them invalid.

Checks use package repository metadata. Timely results require repository access and a running cron service.

## Installation

### Debian and Ubuntu

This repository is private. The download commands require GitHub CLI authenticated with an account that can read the repository, using `gh auth login`.

Download the [DEB package, version 0.5.17-2](install/updates-monitor_0.5.17-2_all.deb). The commands below stop on a download or checksum failure and replace the destination file only after validation.

```sh
(
    set -eu
    gh auth status
    work=$(mktemp -d ./updates-monitor-download.XXXXXXXX)
    trap 'rm -rf -- "$work"' EXIT
    gh api -H 'Accept: application/vnd.github.raw' \
        'repos/g1n10l/updates-monitor/contents/install/updates-monitor_0.5.17-2_all.deb?ref=0c22d15' \
        > "$work/updates-monitor.deb"
    printf '%s  %s\n' \
        '76328c8f716046aca016796a1c0f0e088a3c311c0910d19675df660c97a9c0f6' \
        "$work/updates-monitor.deb" | sha256sum -c -
    dpkg-deb --info "$work/updates-monitor.deb" >/dev/null
    mv -- "$work/updates-monitor.deb" ./updates-monitor.deb
    sudo apt-get install -y "$(pwd)/updates-monitor.deb"
)
```

The archive installer also checks the adjacent `.deb.sha256` file and the DEB format before invoking APT. Keep the package and its checksum file together.

Debian revision `0.5.13-2` fixes installation and result writes after SELinux tools have been removed while the kernel remains in permissive mode. Systems without SELinux need no SELinux tools. With SELinux enabled and its tools present, runtime labeling remains supported. Enforcing mode requires `semanage` and `restorecon`; the installer reports missing tools rather than disabling enforcement. The package was installed and checked on Debian 13 hosts with SELinux enforcing, permissive and disabled. Automated regression tests cover these variants. Ubuntu installation has not been tested.

The package depends on `python3`, `python3-apt`, `apt`, `systemd`, `util-linux`, and `cron`. If `dpkg` reports missing dependencies, run `sudo apt --fix-broken install`.

The RUN installer can be built from [source](source%20code/build-installer.py). It installs into `/usr/local` and does not provide a package manager uninstall command.

To remove the package and its configuration:

```sh
sudo apt purge updates-monitor
```

### Red Hat family

The [RPM package, version 0.5.17-2](install/updates-monitor-0.5.17-2.noarch.rpm), is experimental. It has not been verified on a running RHEL system and is unsigned.

```sh
gh api -H 'Accept: application/vnd.github.raw' 'repos/g1n10l/updates-monitor/contents/install/updates-monitor-0.5.17-2.noarch.rpm?ref=main' > updates-monitor-0.5.17-2.noarch.rpm
echo 'c56bfb3625c7ab026506f466bbd0ceccb658870d37075c03b0d934671284e680  updates-monitor-0.5.17-2.noarch.rpm' | sha256sum -c -
sudo dnf install updates-monitor-0.5.17-2.noarch.rpm
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

`status` displays current pending package counts, the last successful check, restart status, the interval, and service status. The service performs one check and may show as `inactive` after it finishes. If a check fails, `status` also shows recent errors from `journalctl`.

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

On Debian and Ubuntu, the script identifies security archives by the `-security` suffix and examines a `full-upgrade` plan. All kernel upgrades and new kernel packages are counted in the kernel category, regardless of source. Custom repositories and some Ubuntu ESM updates may be counted as regular updates. New dependencies are included; removals and packages kept back by APT are excluded.

For the RPM version, security classification depends on DNF repository `updateinfo` metadata. Each check counts current package candidates, not vulnerabilities.

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

## Updating problem counts in Zabbix

Import the updated template, then run `setup-zabbix-correlation.py --url https://YOUR-ZABBIX/api_jsonrpc.php` from the source directory with a Super admin token in `ZABBIX_API_TOKEN`. Use `--ca-file` for a private CA. DEB and RPM packages install a copy in `/usr/share/updates-monitor/`. This creates or updates the scoped rule defined in `zabbix-updates-monitor-correlation.json`; a template import alone cannot install the global correlation rule.

The rule matches both the old and new `updates-monitor.component=package-count` tags and the same `updates-monitor.scope` tag, containing the host and category. It closes only the previous matching problem. Count items discard unchanged values, so periodic reads do not create duplicate events. The Problems widget can keep its normal layout with operational data hidden and the count in the problem name. Existing untagged problems from earlier templates require a one-time close after migration; their history remains available.

The three categories remain disjoint. Repeated checks do not add the same packages again. The aggregate Razem row and updates.monitor.total item have been removed.

## Distribution release upgrades

The CLI includes a separate DISTRIBUTION / DIST-UPGRADE status, and the template has a Warning trigger for an available distribution release upgrade. Debian checks the official HTTPS stable Release metadata and, for older systems, oldstable, offering only the next major version. Point releases do not raise the alert. Ubuntu uses `do-release-upgrade -c`, respecting the host release policy; install `ubuntu-release-upgrader-core` to enable this check. Missing tools, unsupported systems, network and metadata errors report unknown, rather than no upgrade. Unknown does not close an existing upgrade problem. Release checks run with the package scan. No repositories are changed and no release upgrade is started. The experimental RPM build reports this check as unsupported.

The dependent items are `updates.monitor.dist_upgrade.available` (0: no upgrade, 1: available, 2: unknown), `.current`, `.target`, and `.error`. Existing older raw states skip these fields until the host is updated. `apt dist-upgrade` remains the package plan within configured repositories; the release status is separate and is excluded from package totals.

## Monitor and template versions

The first output line shows the installed updates-monitor version, including its package revision. The aggregate Razem row and `updates.monitor.total` item are removed. The template compares `updates.monitor.version_code` with its own version and the minimum required version. A lower script or a lower template raises the same Warning trigger. An old script that does not report its version is treated as version zero. Numeric comparison includes all four components, so 0.5.10 is newer than 0.5.9 and revision 2 is newer than revision 1. This checks the updates-monitor template, not the Zabbix server software version.

For automatic checks against GitHub Releases, configure `{$UPDATES.MONITOR.GITHUB.TOKEN}` as a secret macro using a dedicated fine-grained token with read-only Contents access to the private repository. Enable the HTTP item `updates.monitor.latest.raw`, its two dependent latest items, and both GitHub-specific triggers, then set `{$UPDATES.MONITOR.GITHUB.CHECK}` to 1. TLS certificate verification remains enabled. Checks run hourly and use published stable releases. If neither side is current, the version trigger fires even when their versions match. A separate trigger reports missing release data after one day. GitHub checks are disabled until credentials are configured; script/template comparison and the required minimum version remain active. Never embed a token in a template export.
