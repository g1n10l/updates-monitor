UPDATES-MONITOR — DEBIAN, UBUNTU I ZABBIX 7.4

To katalog źródeł. Polecenia budowania poniżej wykonuj w tym katalogu.
Gotowe instalatory i sumy kontrolne znajdują się w ../install/.

1. DZIAŁANIE

Usługa odświeża indeksy APT i analizuje plan full-upgrade bez instalowania
ani usuwania pakietów. Cron uruchamia harmonogram co minutę, a program zleca
właściwą kontrolę według zapisanego interwału, domyślnie co dzień. Po
restarcie pierwsza kontrola jest zlecana około minuty po uruchomieniu. Wpis
@reboot i cykliczny wpis cron współpracują, aby nie uruchomić dwóch kontroli.
Uruchomienie może opóźnić się, gdy system oczekuje na sieć lub cron nie działa.
Cron wykrywa również zmianę bazy /var/lib/dpkg/status po operacji na
pakietach. Po zwolnieniu blokad dpkg i APT zleca dodatkową kontrolę bez
restartu, zwykle w ciągu minuty. Zmiana bazy może oznaczać także usunięcie
lub konfigurację pakietu. Gdy poprzednia kontrola trwa, kolejna poczeka.
Jeśli kontrola zakończy się błędem, ostatnie wyniki pozostają nieaktualne.

Każda udana kontrola zapisuje bieżącą liczbę pakietów do zainstalowania.
Pięć oczekujących pakietów i trzy nowe daje osiem; ponowna kontrola tych
samych ośmiu nadal pokazuje osiem. Zainstalowane pakiety przestają być liczone.
Kategorie regular, security i kernel_security są rozłączne. Nie ma pozycji Razem.

Stan znajduje się w /run/updates-monitor/state.json i znika podczas restartu.
Przed pierwszą udaną kontrolą liczniki wynoszą 0, ale valid wynosi 0: nie jest
to potwierdzenie braku aktualizacji. Kategorie są rozłączne:
- regular: zwykłe aktualizacje;
- security: aktualizacje bezpieczeństwa inne niż pakiety kernela;
- kernel_security: wszystkie dostępne aktualizacje pakietów kernela, również
  spoza repozytorium bezpieczeństwa (nazwa klucza zachowana dla Zabbixa).

Bezpieczeństwo rozpoznawane jest po nazwie archiwum APT kończącej się na
-security. Niestandardowe repozytoria i część Ubuntu ESM mogą zostać zaliczone
do zwykłych. Liczone są aktualizacje i wszystkie nowe zależności planu APT
full-upgrade, w tym pakiety kernela. Suma odpowiada liczbie pakietów z linii
Inst symulacji apt-get -s dist-upgrade dla tych samych metadanych i ustawień.
Planowane usunięcia i pakiety zatrzymane przez APT nie są liczone.

Przy błędzie kontroli zachowywane są ostatnie poprawne liczniki, a valid
zmienia się na 0. checked_at to czas ostatniej udanej kontroli Unix time.

2. INSTALACJA

Wymagane są Debian albo Ubuntu z systemd, cron, APT, python3, python3-apt,
flock i działającymi repozytoriami. Instalatory mogą doinstalować wymagane
pakiety z dostępnych repozytoriów. Przy pracy offline zależności muszą być
już dostępne lokalnie. Przy aktywnym SELinux potrzebne są semanage i restorecon.
Instalator nie sprawdza internetu, nie dodaje repozytorium Zabbiksa ani nie
instaluje agenta. Jeśli agent jest zainstalowany, instaluje konfigurację
odczytu i restartuje działającego agenta. Po późniejszej instalacji agenta
uruchom instalator ponownie. Adres Server i ewentualny ServerActive ustaw
w konfiguracji agenta osobno.

Przy aktualizacji z poprzedniej wersji korzystającej z timera instalator
przenosi jego obsługiwany interwał i ustawienie autostartu do konfiguracji
cron, a następnie wyłącza wcześniejsze timery updates-monitor.

PAKIET DEB:
  python3 build-deb.py
  sudo dpkg -i ./../install/updates-monitor_0.5.17-2_all.deb

Jeśli dpkg zgłosi brakujące zależności, doinstaluj je poleceniem:
  sudo apt --fix-broken install

Można też wypakować ../install/updates-monitor-deb-installer.tar.gz do nowego
katalogu i uruchomić sudo bash install-deb.sh. Paczka umieszcza szablon
w /usr/share/updates-monitor/zabbix-updates-monitor.json. Pakiet .deb nie
zastępuje instalacji w /usr/local: przed zmianą sposobu instalacji należy
usunąć starą instalację. Usuwanie pakietu:
  sudo apt remove updates-monitor
  sudo apt purge updates-monitor

INSTALATOR RUN:
  sudo bash updates-monitor-installer.run
  bash updates-monitor-installer.run --check
  bash updates-monitor-installer.run --extract /tmp/updates-monitor-pliki

Aby zbudować instalator RUN w katalogu źródłowym: python3 build-installer.py.
Plik man po instalacji jest dostępny przez: man updates-monitor.

3. OBSŁUGA

  sudo updates-monitor status
  sudo updates-monitor interval 6h
  sudo updates-monitor interval 1D
  sudo updates-monitor interval 30D
  systemctl status cron.service
  systemctl status updates-monitor.service
  journalctl -u updates-monitor.service -n 50 --no-pager
  cat /etc/cron.d/updates-monitor
  cat /etc/updates-monitor/schedule.json
  cat /run/updates-monitor/state.json
  cat /run/updates-monitor/health.json

status wykonuje kontrolę także przy wyłączonym harmonogramie i pokazuje liczby,
stan usługi, stan cron i interwał. Jeśli kontrola się nie powiedzie, na końcu
pokazuje do 10 ostatnich błędów usługi z journalctl; mogą obejmować wcześniejsze
uruchomienia. Usługa jest typu oneshot i po zakończeniu ma stan inactive.

Interwały: 2h, 6h, 12h, 1D, 5D, 10D, 15D, 30D. Wartość przechowuje plik
/etc/updates-monitor/schedule.json. Moment ostatniej próby z harmonogramu
w danym uruchomieniu zapisuje /run/updates-monitor/last-attempt. Cron uruchamia mechanizm
co minutę; rzeczywisty czas kontroli może mieć opóźnienie do minuty. Po
restarcie zegar interwału jest zerowany i wykonywana jest kontrola po minucie.
Polecenie sudo updates-monitor interval 0 wyłącza automatyczne kontrole.
Ustawienie interwału, np. 6h, ponownie je włącza. Ręczne status nadal działa.
Wersję pakietu sprawdzisz: dpkg-query -W updates-monitor (Debian/Ubuntu)
lub rpm -q updates-monitor (RHEL).
Podczas aktualizacji poprzednie wartości są zamieniane: 1h na 2h,
15h na 12h, 1d na 1D, 3d na 5D, 8d na 10D; 6h pozostaje bez zmian.
Wcześniej wyłączony harmonogram można ponownie włączyć ręcznie:
  sudo systemctl enable --now cron.service
  sudo /usr/lib/updates-monitor/scheduler.py enable 1
  sudo systemctl start --no-block updates-monitor-scheduler.service
W instalacji RUN zamiast /usr/lib należy użyć /usr/local/lib.

4. ZABBIX

Pliki konfiguracji na monitorowanym serwerze:
  /etc/zabbix/updates-monitor/agent.conf — parametry odczytu wyników
  /etc/zabbix/zabbix_agentd.conf — konfiguracja Zabbix agent
  /etc/zabbix/zabbix_agent2.conf — konfiguracja Zabbix agent 2

Instalator dodaje Include=/etc/zabbix/updates-monitor/agent.conf do pliku
konfiguracji każdego wykrytego agenta. Parametry Server i ServerActive
należy ustawić osobno w odpowiednim pliku konfiguracji agenta.
Ponowna instalacja pakietu DEB odtwarza brakujący agent.conf bez zmiany
istniejącego pliku konfiguracyjnego.

W Data collection → Templates → Import zaimportuj zabbix-updates-monitor.json,
a następnie przypisz szablon „updates-monitor” do hosta.
Agent pasywny jest odpytywany co minutę; odczyt nie uruchamia APT.

Trzy wyzwalacze dotyczą aktualizacji regularnych (Information, niebieski),
bezpieczeństwa (Warning, żółty) i kernela (Disaster, czerwony).
Nazwa problemu zawiera bieżącą liczbę pakietów. Zmiana dodatniej liczby
tworzy nowe zdarzenie i zamyka poprzednie tego hosta i kategorii; niezmieniona
liczba nie tworzy następnego. Wymaga to reguły korelacji z pliku
zabbix-updates-monitor-correlation.json. Po imporcie szablonu skonfiguruj ją
narzędziem setup-zabbix-correlation.py --url URL_API, podając token Super admin
w zmiennej ZABBIX_API_TOKEN; --ca-file wskazuje prywatny certyfikat CA.
Dodatkowe wyzwalacze zgłaszają błąd kontroli, wyłączony harmonogram, brak
agenta, brak świeżego stanu harmonogramu oraz nieaktualny wynik. Wynik jest
nieaktualny, gdy ostatnia udana kontrola jest starsza od interwału o 20 minut.
Niepoprawny wynik nie zeruje liczników w Zabbiksie, a problemy o aktualizacjach
zamykają się dopiero po poprawnym sprawdzeniu z wynikiem zero.

Test lokalny agenta:
  zabbix_agentd -t updates.monitor.raw
  zabbix_agentd -t updates.monitor.health
Dla agent2 użyj zabbix_agent2. Dane widać także w Latest data.

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
