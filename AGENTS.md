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
