# updates-monitor

This is the source directory. Commands below assume this working directory;
ready-built installers are in [`../install/`](../install/).

Monitor Linux package updates with Zabbix. The tool reports current pending package counts in three separate categories: regular updates, security updates, and all kernel updates. It refreshes repository metadata but does not install or remove updates.

## Platforms and packages

- **Debian and Ubuntu:** APT, systemd and cron. Install the [DEB package](../install/updates-monitor_0.5.17-2_all.deb). The optional RUN installer can be built with [build-installer.py](build-installer.py).
- **RHEL 8/9 and compatible systems:** an [RPM package](../install/updates-monitor-0.5.17-2.noarch.rpm) using DNF 4 and crond is provided as an experimental build. Its classification has been tested with simulated data, but installation and operation on a live RHEL system have not yet been verified. The RPM is unsigned. See the [Red Hat build notes](redhat/README.txt).

The installers do not install a Zabbix agent or add a Zabbix repository. They configure an existing Zabbix agent or agent 2; set `Server` and, if applicable, `ServerActive` in the agent configuration separately. The RUN installer does not currently include an uninstaller.

## Install and remove

### Debian family

On Debian, Ubuntu and compatible systems, install the downloaded DEB package:

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

The repository is private. Download binaries through authenticated GitHub access, then verify the checksum. A GitHub HTML view is not a DEB package. Proceed with installation only if the checksum reports `OK`. If `dpkg` reports missing dependencies, install them with `sudo apt --fix-broken install`.

To uninstall the DEB package and remove its saved schedule:

```sh
sudo apt purge updates-monitor
```

After building the optional RUN installer, install using `sudo bash ../install/updates-monitor-installer.run`. This RUN installer does not include an uninstaller.

### Red Hat family

On RHEL 8/9 and compatible systems, install the experimental RPM package:

```sh
sudo dnf install updates-monitor-0.5.17-2.noarch.rpm
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

Each successful check counts the packages currently waiting to be installed. Five waiting packages plus three new ones means eight; checking those same eight again still reports eight. Installed packages disappear from the count. The total is the sum of the three disjoint categories. Debian includes upgrades and all new dependencies in the APT full-upgrade plan, matching `apt-get -s dist-upgrade` with the same metadata and configuration. Failed checks retain the last counts and mark them invalid.

The schedule is stored in `/etc/updates-monitor/schedule.json`. Results and health are in `/run/updates-monitor/state.json` and `/run/updates-monitor/health.json`; they are recreated after reboot. A result with `valid: 0` does not confirm that there are no updates. Existing schedule settings are preserved or migrated during an upgrade; see [README.txt](README.txt) for details.

## Zabbix

Import [zabbix-updates-monitor.json](zabbix-updates-monitor.json) into Zabbix 7.4 and link the template **updates-monitor** to the host. The template uses the same agent keys for the experimental RPM variant. The template includes one item and trigger for each package category, plus health and freshness alerts. A changed current count creates a new problem with the new sum in its name and closes the previous problem for that host and category. Configure the global correlation rule described below after importing the template.

The installer adds `Include=/etc/zabbix/updates-monitor/agent.conf` to each detected agent configuration. Reinstalling the DEB or RPM restores a missing `agent.conf` without replacing an existing one. To test a configured agent locally:

```sh
zabbix_agentd -t updates.monitor.raw
zabbix_agentd -t updates.monitor.health
```

Use `zabbix_agent2` instead when running agent 2. No agent is installed automatically.

## Classification limits

On Debian and Ubuntu, APT security archives are identified by the `-security` suffix. Some custom sources and Ubuntu ESM updates may be classified as regular updates. The check models `full-upgrade` and counts upgrades and all new dependencies, including kernel packages. Removals and packages kept back by APT are excluded. The internal `kernel_security` key remains for compatibility with existing Zabbix items.

On RHEL-compatible systems, the DNF variant reports upgrade candidates rather than a resolved transaction. Security classification depends on repository `updateinfo` metadata; without it, security updates can be classified as regular. Kernel candidates are counted in the kernel category regardless of security metadata. Each check counts current package candidates once. Repeated checks of the same candidates do not increase the count.

## Documentation and author

The manual is available after installation with `man updates-monitor`. More detailed Polish instructions are in [README.txt](README.txt). Created by **G1n10L**.

## Restart required after updates

The scheduler reports reboot status in `updates.monitor.reboot_required` through the existing health item. Zabbix raises a warning containing the host name when a restart is required and a valid scan shows zero regular, security and kernel updates. It closes the warning only after both reboot sources confirm no restart is needed and a valid scan exists; unknown data do not confirm recovery. The status is refreshed on each scheduler tick, normally once per minute, independently of the update scan interval. The agent and Zabbix polling add delay.

On Debian and Ubuntu the check uses `/run/reboot-required`, which only reflects packages that create the marker. On RHEL-compatible systems it runs `dnf needs-restarting -r` from `dnf-plugins-core` as the scheduler user. A missing tool, unrecognized result, failed check or old agent reports status 2 (unknown), not a clear result. Monitoring covers host reboots; individual services may also require a restart. The alert does not restart a host.

Update the installed monitor on each host and import the updated template. A template imported before the new monitor reports an unknown reboot status until the host is upgraded. Existing agent keys are unchanged.

## New kernel restart recommendation

The Zabbix item `updates.monitor.kernel_update_pending` compares the running kernel version with kernel images of the same flavour or architecture in `/boot`. A newer image yields 1; no newer image yields 0; an unsupported version format, missing images or comparison error yields 2 (unknown). The combined warning names the host when either this value or the system reboot indicator is 1, a valid scan after the latest package database change shows all three categories at zero, and the check service is idle. Both restart sources must report 0 before the warning closes; unknown data do not close it.

This is a recommendation based on files in `/boot`, not proof that the bootloader is configured to load the newer image. Retained or manually installed images can influence the result. It is independent of the system reboot-required marker; both sources feed one warning. A separate boot partition must be mounted for the check. The scheduler refreshes the result on each tick, normally once per minute.

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
