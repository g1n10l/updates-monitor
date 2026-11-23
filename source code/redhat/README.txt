updates-monitor — wersja RPM dla systemów z DNF 4

Wariant przeznaczony do budowania na RHEL 8/9 i zgodnych systemach. Wymaga
systemd, dnf, cronie, python3 i util-linux. Nie instaluje agenta Zabbix.

Budowanie na systemie docelowym z pakietem rpm-build:
  ./redhat/build-rpm.sh
Instalacja i usunięcie powstałego pakietu:
  sudo dnf install ./../install/updates-monitor-0.5.12-1.noarch.rpm
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
Każda udana kontrola dodaje aktualne liczby do poprzednich wartości we
wszystkich trzech kategoriach. Wynik 0 zeruje kategorię. Ponowne kontrole
tych samych pakietów powiększają sumę; nie jest to liczba unikalnych
pakietów aktualnie oczekujących.
