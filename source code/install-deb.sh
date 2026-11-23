#!/bin/bash
# Ask before apt obtains the dpkg lock; then install the local .deb package.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Uruchom: sudo bash install-deb.sh [ścieżka-do-pakietu.deb]' >&2; exit 1; }
[[ $# -le 1 ]] || { echo 'Podaj najwyżej jedną ścieżkę do pakietu .deb.' >&2; exit 2; }
cd "$(dirname "$(readlink -f "$0")")"
if [[ -f ./updates-monitor_0.5.6-1_all.deb ]]; then
    default_pkg=./updates-monitor_0.5.6-1_all.deb
else
    default_pkg=../install/updates-monitor_0.5.6-1_all.deb
fi
pkg=${1:-$default_pkg}
pkg=$(readlink -f "$pkg")
[[ -f $pkg ]] || { echo 'Nie znaleziono pakietu .deb.' >&2; exit 1; }
if [[ $(dpkg-query -W -f='${db:Status-Status}' updates-monitor 2>/dev/null || true) == installed ]]; then
    apt-get install -y --reinstall "$pkg"
else
    apt-get install -y "$pkg"
fi
