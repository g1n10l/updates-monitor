# Weryfikacja instalatorów Debiana

Przy każdej kompilacji i publikacji instalatora DEB:

- Sprawdź wynikowy pakiet narzędziem `dpkg-deb --info`, `dpkg-deb --control` i `dpkg-deb --extract` na Debianie lub Ubuntu. Sam odczyt archiwum w Pythonie nie zastępuje tej kontroli.
- Sprawdź składnię skryptów preinst, postinst, prerm i postrm oraz poprawność wersji i zawartości paczki.
- Wygeneruj SHA-256 dla gotowego pliku. Po publikacji pobierz opublikowany pakiet i porównaj jego sumę z lokalnym plikiem. Ponownie sprawdź go przez dpkg-deb.
- Podawaj bezpośredni link do pliku binarnego, nigdy link do podglądu GitHuba `/blob/`. Dla prywatnego repozytorium używaj uwierzytelnionego pobierania, np. GitHub CLI.
- Zweryfikuj, że pobrany plik jest pakietem Debian, a nie stroną HTML lub odpowiedzią błędu zapisaną z rozszerzeniem `.deb`.
- Przed publikacją sprawdź, czy wersjonowane paczki, archiwa instalatora, wrapper i sumy kontrolne wskazują tę samą wersję. Aktualizuj też niewersjonowane aliasy, jeśli są dostarczane.
- Nie deklaruj udanej instalacji na podstawie samej kontroli archiwum. Podaj osobno, czy wykonano pełną instalację lub aktualizację na Debianie. Jeśli środowisko do walidacji jest niedostępne, zgłoś brak weryfikacji i nie opisuj paczki jako zweryfikowanej.

W historii projektu pliki pobrane z podglądu GitHuba zawierały HTML zamiast DEB. To potwierdzona przyczyna wcześniejszego błędu `is not a Debian format archive`. Nie zakładaj bez sprawdzenia, że każdy kolejny kod błędu 1 lub 2 ma tę samą przyczynę.

# Zgodność liczników z APT

- Liczniki pokazują bieżące pakiety do zainstalowania, a nie sumę wyników kolejnych kontroli. Pięć oczekujących pakietów plus trzy nowe daje osiem; ponowna kontrola tych samych pakietów nadal pokazuje osiem.
- Kategorie regular, security i kernel_security są rozłączne. Ich suma w updates-monitor i Zabbiksie musi odpowiadać planowi APT full-upgrade, łącznie ze wszystkimi nowymi zależnościami. Kontrolę wykonuj przez apt-get -s dist-upgrade przy tych samych metadanych i ustawieniach.
- Zachowaj testy powtórnych kontroli, wzrostu i spadku liczby pakietów, wyniku zero oraz uwzględniania nowych zależności. Błąd kontroli zachowuje poprzednie liczniki i oznacza wynik jako nieaktualny.
- Zmiana liczby zastępuje poprzedni alarm nowym alarmem tego samego hosta i kategorii. Powtórny odczyt niezmienionej liczby nie tworzy zdarzenia. Zachowaj liczbę w nazwie alarmu i dotychczasowy układ widgetu.

# Wersja programu i szablonu

- Przy wydaniu aktualizuj spójnie source code/VERSION, stałą VERSION w obu skryptach, wersję CLI, pakietów, vendor szablonu i makra wersji oraz wersji minimalnej. Test tests/test_versions.py sprawdza ich zgodność i porównanie obu kierunków.
- Wersja programu z rewizją ma być w pierwszym wierszu podsumowania. Nie przywracaj pozycji Razem.
- Nie umieszczaj tokenów GitHuba w plikach eksportowanego szablonu ani repozytorium. Odczyt prywatnych wydań jest wyłączony do skonfigurowania dedykowanego tokena tylko do odczytu.
