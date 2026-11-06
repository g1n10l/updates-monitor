# updates-monitor

`updates-monitor` sprawdza dostępne aktualizacje systemu i przekazuje ich liczbę do Zabbixa. Nie instaluje ani nie usuwa pakietów.

## Co monitoruje

Wyniki są podzielone na trzy kategorie:

| Kategoria | Znaczenie w Zabbixie |
| --- | --- |
| Aktualizacje regularne | Niebieski wyzwalacz z liczbą pakietów |
| Aktualizacje bezpieczeństwa | Żółty wyzwalacz z liczbą pakietów |
| Aktualizacje bezpieczeństwa kernela | Czerwony wyzwalacz z liczbą pakietów |

Zabbix otrzymuje również czas ostatniej kontroli, stan harmonogramu i stan usługi. Publiczny [szablon Zabbixa](template/updates-monitor.json) jest również dołączony do pakietu instalacyjnego jako `/usr/share/updates-monitor/zabbix-updates-monitor.json`. Instalator konfiguruje odczyt danych przez istniejącego Zabbix agenta lub agenta 2. Agenta trzeba zainstalować i skonfigurować osobno.

## Kiedy sprawdza aktualizacje

- Domyślny interwał wynosi **1 dzień**. Dostępne wartości to `2h`, `6h`, `12h`, `1D`, `5D`, `10D` i `15D`.
- Cron sprawdza harmonogram co minutę. Pierwszą kontrolę zleca około minuty po uruchomieniu systemu.
- Na Debianie i Ubuntu zmiana bazy pakietów dpkg zleca dodatkową kontrolę po zwolnieniu blokad menedżera pakietów. Dzięki temu instalacja aktualizacji może zmienić liczniki bez restartu systemu, zwykle w ciągu minuty.
- Po restarcie liczniki zaczynają od zera, a wynik pozostaje oznaczony jako nieważny do pierwszej udanej kontroli. Po błędzie zachowane liczby także są oznaczone jako nieważne.

Kontrola korzysta z danych repozytoriów pakietów. Dostęp do nich oraz działający cron są potrzebne do terminowych wyników.

## Instalacja

### Debian i Ubuntu

Pobierz [pakiet DEB 0.5.2-1](installers/updates-monitor_0.5.2-1_all.deb). Plik instalacyjny musi być pakietem DEB, a nie stroną HTML z GitHuba.

```sh
curl -fL -o updates-monitor.deb https://raw.githubusercontent.com/g1n10l/updates-monitor/main/installers/updates-monitor_0.5.2-1_all.deb
echo 'f299b18fa236dc75b5d6543978719c6b01e06b03913d2d047154f997c9cf6415  updates-monitor.deb' | sha256sum -c -
sudo dpkg -i updates-monitor.deb
```

Pakiet wymaga `python3`, `python3-apt`, `apt`, `systemd`, `util-linux` i `cron`. Jeśli `dpkg` zgłosi brakujące zależności, użyj `sudo apt --fix-broken install`.

Deinstalacja wraz z konfiguracją pakietu:

```sh
sudo apt purge updates-monitor
```

### Rodzina Red Hat

Pakiet [RPM 0.5.0-1](installers/updates-monitor-0.5.0-1.noarch.rpm) jest wersją eksperymentalną. Jego działania nie zweryfikowano na działającym systemie RHEL; pakiet nie jest podpisany.

```sh
curl -fL -o updates-monitor-0.5.0-1.noarch.rpm https://raw.githubusercontent.com/g1n10l/updates-monitor/main/installers/updates-monitor-0.5.0-1.noarch.rpm
echo '566e2eb97a7642466581aa1b5a0d6554d574eb3e5e588c071640f26ece33d3d4  updates-monitor-0.5.0-1.noarch.rpm' | sha256sum -c -
sudo dnf install updates-monitor-0.5.0-1.noarch.rpm
```

Deinstalacja: `sudo dnf remove updates-monitor`. Po usunięciu RPM pliki konfiguracji i harmonogramu mogą pozostać na dysku.

## Użycie

```sh
sudo updates-monitor status
sudo updates-monitor interval 6h
sudo updates-monitor interval 1D
man updates-monitor
```

`status` uruchamia bieżącą kontrolę również przy wyłączonym harmonogramie. Wyświetla liczniki, czas ostatniej udanej kontroli, interwał i stan usług. Jeśli uruchomienie usługi się nie powiedzie, pokazuje ostatnie błędy z `journalctl`.

Usługa wykonuje pojedynczą kontrolę i po jej zakończeniu może mieć stan `inactive`. Harmonogram działa przez cron. Dziennik można odczytać poleceniem:

```sh
journalctl -u updates-monitor.service -n 50 --no-pager
```

## Zabbix i pliki

Po instalacji zaimportuj [szablon](template/updates-monitor.json) lub `/usr/share/updates-monitor/zabbix-updates-monitor.json` do Zabbixa i przypisz szablon `Updates monitor Debian Ubuntu` do hosta. Ustaw `Server` oraz, jeśli używasz aktywnych kontroli, `ServerActive` w konfiguracji agenta.

| Ścieżka | Zawartość |
| --- | --- |
| `/etc/cron.d/updates-monitor` | Zadania harmonogramu |
| `/etc/updates-monitor/schedule.json` | Włączony harmonogram i interwał |
| `/etc/zabbix/updates-monitor/agent.conf` | Klucze agenta Zabbix |
| `/run/updates-monitor/state.json` | Liczniki i ważność ostatniego wyniku |
| `/run/updates-monitor/health.json` | Stan usługi i harmonogramu |

## Ograniczenia liczenia

Na Debianie i Ubuntu skrypt rozpoznaje archiwa bezpieczeństwa po nazwie kończącej się na `-security` i analizuje plan `full-upgrade`. Niestandardowe źródła oraz część Ubuntu ESM mogą zostać zaliczone do aktualizacji regularnych. Nowe pakiety kernela z archiwum bezpieczeństwa są liczone; część innych nowych zależności i pakietów wstrzymanych może zostać pominięta.

W wersji RPM klasyfikacja bezpieczeństwa zależy od metadanych `updateinfo` w repozytorium DNF. Liczniki oznaczają pakiety, a nie liczbę podatności.

Projekt stworzył **G1n10L**.
