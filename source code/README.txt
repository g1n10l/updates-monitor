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

Każda udana kontrola liczy dostępne pakiety od nowa i dodaje wynik do
poprzedniej wartości osobno dla każdej kategorii. Na przykład poprzednie 3
plus 5 z nowej kontroli daje 8. Gdy w kategorii nie ma już dostępnych
pakietów, jej licznik wraca do 0. Ponowne kontrole tych samych zaległych
pakietów także powiększają sumę. Licznik nie oznacza liczby unikalnych
pakietów ani liczby pakietów oczekujących w danej chwili.

Stan znajduje się w /run/updates-monitor/state.json i znika podczas restartu.
Przed pierwszą udaną kontrolą liczniki wynoszą 0, ale valid wynosi 0: nie jest
to potwierdzenie braku aktualizacji. Kategorie są rozłączne:
- regular: zwykłe aktualizacje;
- security: aktualizacje bezpieczeństwa inne niż pakiety kernela;
- kernel_security: wszystkie dostępne aktualizacje pakietów kernela, również
  spoza repozytorium bezpieczeństwa (nazwa klucza zachowana dla Zabbixa).

Bezpieczeństwo rozpoznawane jest po nazwie archiwum APT kończącej się na
-security. Niestandardowe repozytoria i część Ubuntu ESM mogą zostać zaliczone
do zwykłych. Liczone są aktualizowane pakiety oraz nowe pakiety kernela
niezależnie od repozytorium. Inne nowe zależności, planowane usunięcia i część
wstrzymanych pakietów nie są liczone. Pojedyncza kontrola liczy pakiety,
nie podatności; zapisana suma może wielokrotnie uwzględniać ten sam pakiet.

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
  sudo dpkg -i ./../install/updates-monitor_0.5.10-1_all.deb

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

Interwały: 2h, 6h, 12h, 1D, 5D, 10D, 15D. Wartość przechowuje plik
/etc/updates-monitor/schedule.json. Moment ostatniej próby z harmonogramu
w danym uruchomieniu zapisuje /run/updates-monitor/last-attempt. Cron uruchamia mechanizm
co minutę; rzeczywisty czas kontroli może mieć opóźnienie do minuty. Po
restarcie zegar interwału jest zerowany i wykonywana jest kontrola po minucie.
Zmiana interwału nie włącza wyłączonego harmonogramu.
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
Nazwa problemu zawiera sumę z chwili zgłoszenia. Bieżącą sumę pokazują
dane operacyjne; w widżecie Problemy należy włączyć ich wyświetlanie.
Dodatkowe wyzwalacze zgłaszają błąd kontroli, wyłączony harmonogram, brak
agenta, brak świeżego stanu harmonogramu oraz nieaktualny wynik. Wynik jest
nieaktualny, gdy ostatnia udana kontrola jest starsza od interwału o 20 minut.
Niepoprawny wynik nie zeruje liczników w Zabbiksie, a problemy o aktualizacjach
zamykają się dopiero po poprawnym sprawdzeniu z wynikiem zero.

Test lokalny agenta:
  zabbix_agentd -t updates.monitor.raw
  zabbix_agentd -t updates.monitor.health
Dla agent2 użyj zabbix_agent2. Dane widać także w Latest data.
