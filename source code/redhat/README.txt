updates-monitor — wersja RPM dla systemów z DNF 4

Wariant przeznaczony do budowania na RHEL 8/9 i zgodnych systemach. Wymaga
systemd, dnf, cronie, python3 i util-linux. Nie instaluje agenta Zabbix.

Budowanie na systemie docelowym z pakietem rpm-build:
  ./redhat/build-rpm.sh
Instalacja i usunięcie powstałego pakietu:
  sudo dnf install ./../install/updates-monitor-0.5.17-2.noarch.rpm
  sudo dnf remove updates-monitor

Polecenia: sudo updates-monitor status oraz sudo updates-monitor interval 1D.
Dostępne interwały: 2h, 6h, 12h, 1D, 5D, 10D, 15D, 30D; domyślnie 1D.
Cron uruchamia sprawdzenie po restarcie i według wybranego interwału.
Wyniki przekazywane są przez istniejący szablon zabbix-updates-monitor.json.
Ponowna instalacja pakietu RPM odtwarza brakujący agent.conf bez zmiany
istniejącego pliku konfiguracyjnego.
Należy przypisać szablon do hosta; mimo nazwy Debian Ubuntu klucze są zgodne.

DNF repoquery wskazuje dostępne aktualizacje, a nie rozwiązaną transakcję.
Pakiety liczone są według nazwy i architektury. Klasyfikacja bezpieczeństwa
wymaga metadanych updateinfo w repozytoriach; jeśli ich brakuje, aktualizacje
bezpieczeństwa mogą zostać zakwalifikowane jako regularne. Nie dodawaj
repozytoriów bez odpowiednich metadanych, jeśli podział ma być wiarygodny.
Przy problemie z pobraniem metadanych wynik jest oznaczany jako nieaktualny.
Każda udana kontrola zapisuje bieżące liczby kandydatów aktualizacji.
Powtórne sprawdzenie tych samych pakietów nie zwiększa liczników.
Trzy kategorie są rozłączne; pozycja Razem została usunięta.

Zmiana dodatniej sumy tworzy nowy alarm i zamyka poprzedni alarm hosta
i kategorii. Wymaga reguły korelacji zabbix-updates-monitor-correlation.json,
konfigurowanej przez setup-zabbix-correlation.py. Szczegóły w głównym README.

AKTUALIZACJA DYSTRYBUCJI / DIST-UPGRADE

Osobna pozycja status pokazuje wersję obecną, docelową i dostępność wydania.
Debian porównuje główną wersję z oficjalnymi metadanymi HTTPS stable/oldstable;
proponuje wyłącznie kolejną wersję główną. Wydania punktowe nie wywołują alarmu.
Ubuntu używa do-release-upgrade -c z pakietu ubuntu-release-upgrader-core.
Błąd sieci, brak narzędzia lub nieobsługiwany system oznacza stan nieznany.
RPM zgłasza brak obsługi wykrywania wydania. Kontrola odbywa się przy skanie.
Wyzwalacz Zabbixa zgłasza dostępne wydanie z poziomem Warning; stan nieznany
nie zamyka istniejącego alarmu. Klucze: updates.monitor.dist_upgrade.available
(0: brak, 1: dostępne, 2: nieznane), .current, .target oraz .error. Wymagana
jest aktualizacja skryptu i import szablonu. Nie zmienia repozytoriów ani nie
uruchamia migracji. Samo apt dist-upgrade dotyczy obecnych repozytoriów.

WERSJA PROGRAMU I SZABLONU

Pierwszy wiersz pokazuje wersję updates-monitor z rewizją pakietu. Pozycja Razem
została usunięta. Wyzwalacz porównuje wersję skryptu z wersją szablonu i minimalną
wymaganą wersją. Alarm działa w obu kierunkach. Starszy skrypt bez numeru wersji
jest traktowany jako wersja zero. Nie dotyczy wersji samego serwera Zabbix.
Opcjonalny odczyt GitHub Releases wymaga dedykowanego tokena Contents: read
dla prywatnego repozytorium w tajnym makrze UPDATES.MONITOR.GITHUB.TOKEN.
Należy włączyć pozycje latest.*, oba dodatkowe wyzwalacze GitHuba i ustawić UPDATES.MONITOR.GITHUB.CHECK na 1.
Brak danych o wydaniu po dobie wywołuje osobny alarm. Szczegóły w README.md.
