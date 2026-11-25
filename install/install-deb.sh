#!/bin/bash
# Ask before apt obtains the dpkg lock; then install the local .deb package.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Uruchom: sudo bash install-deb.sh [ścieżka-do-pakietu.deb]' >&2; exit 1; }
[[ $# -le 1 ]] || { echo 'Podaj najwyżej jedną ścieżkę do pakietu .deb.' >&2; exit 2; }
cd "$(dirname "$(readlink -f "$0")")"
if [[ -f ./updates-monitor_0.5.17-2_all.deb ]]; then
    default_pkg=./updates-monitor_0.5.17-2_all.deb
else
    default_pkg=../install/updates-monitor_0.5.17-2_all.deb
fi
pkg=${1:-$default_pkg}
pkg=$(readlink -f "$pkg")
[[ -f $pkg ]] || { echo 'Nie znaleziono pakietu .deb.' >&2; exit 1; }
# Validate before apt takes a lock or changes the system.
checksum="$pkg.sha256"
[[ -f $checksum ]] || { echo "Brak pliku sumy SHA-256: $checksum. Pobierz pakiet razem z jego sumą." >&2; exit 1; }
expected=$(awk 'NR == 1 {print $1}' "$checksum")
[[ $expected =~ ^[[:xdigit:]]{64}$ ]] || { echo 'Nieprawidłowy plik sumy SHA-256.' >&2; exit 1; }
actual=$(sha256sum -- "$pkg")
[[ ${actual%% *} == "$expected" ]] || { echo 'Suma SHA-256 pakietu nie zgadza się. Pobierz pakiet ponownie; instalacja przerwana.' >&2; exit 1; }
dpkg-deb --info "$pkg" >/dev/null || { echo 'Plik nie jest poprawnym pakietem DEB. Instalacja przerwana.' >&2; exit 1; }
[[ $(dpkg-deb --field "$pkg" Package) == updates-monitor ]] || { echo 'To nie jest pakiet updates-monitor.' >&2; exit 1; }
if [[ $(dpkg-query -W -f='${db:Status-Status}' updates-monitor 2>/dev/null || true) == installed ]]; then
    apt-get install -y --reinstall "$pkg"
else
    apt-get install -y "$pkg"
fi
