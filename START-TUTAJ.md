# ElectroCount — drugi komputer

Kod i testy ElectroCount 0.7.5. Windows, Python 3.12 64-bit. Biblioteki pozostają zgodne z runtime 0.7.

Po rozpakowaniu tej aktualizacji uruchamiaj **Uruchom.cmd z nowego folderu**. Stary skrót może uruchamiać wcześniejszy kod. W tytule okna ma być **0.7.5**. Jeśli runtime 0.7 już działa, uruchom Instaluj_AI.cmd, aby pobrać większy model Base (347 MB), potem Uruchom.cmd. Przy pierwszej instalacji albo brakujących bibliotekach uruchom Instaluj.cmd. Otwórz projekt i ponownie kliknij Znajdź — zapisane wyniki nie przeliczają się same.

1. Zaloguj się do GitHuba na swoje konto. W GitHub Desktop wybierz File → Clone repository i repozytorium ElectroCount. Jeśli korzystasz z paczki ZIP, najpierw rozpakuj cały folder do lokalnego katalogu. Po pobraniu aktualizacji zamknij poprzednią aplikację, uruchom Instaluj.cmd i Uruchom.cmd.
2. Zainstaluj Python 3.12 64-bit z python.org wraz z Python Launcher. Sprawdzenie: `py -3.12 --version`.
3. Otwórz folder aplikacji i uruchom Instaluj.cmd. Potrzebny jest internet do pobrania bibliotek. Instalator pobiera również lokalne modele DINOv2 i OCR. Używa krótkiej ścieżki %LOCALAPPDATA%/ElectroCount/py312-07 i kończy testem PASS 12/12.
4. Uruchom Uruchom.cmd. Otwórz lokalny PDF. Analiza używa tej samej jakości na każdym komputerze.
5. W swoim narzędziu do pracy z kodem otwórz ten sam lokalny folder. Przeczytaj CONTINUE.md — opisuje dotychczasowe prace i następne kroki.

## Zasłonięte symbole

Nowo odzyskane elementy są widoczne jako **BEZ PRZYPISANIA** i nie zwiększają licznika grupy. Sprawdź je na rysunku i użyj **Przypisz do grupy**. Aby poprawić sam wzorzec, wybierz **Zliczanie → Wybierz czysty wzorzec tej grupy…**, zaznacz czysty przykład tego samego typu i ponownie kliknij **Znajdź**.

## Praca na dwóch komputerach

GitHub przechowuje kod i historię zmian. Każdy komputer ma własny lokalny folder oraz własne lokalne środowisko Python. Nie umieszczaj aktywnego repozytorium w folderze synchronizowanym przez Google Drive.

Przed pracą w GitHub Desktop: Fetch origin → Pull origin. Utwórz osobną gałąź dla zadania, np. dom/panel-wynikow albo praca/detekcja-etykiet. Po pracy: zapisz zmiany jako commit, następnie Publish branch / Push origin. Zmiany łącz przez pull request do main. Przed połączeniem uruchom testy. Dwa komputery mogą pracować równocześnie na osobnych gałęziach; zmiany w tym samym miejscu mogą wymagać rozwiązania konfliktu. Samo zapisanie pliku nie wysyła go na GitHub.

Paczka ZIP na Dysku Google jest kopią zapasową, nie automatyczną synchronizacją kodu. Po skonfigurowaniu repozytorium pracuj z jego klonami.

## Dokumenty i projekty

Rzeczywiste PDF/DWG/DXF, zapisane projekty, cache, modele i ustawienia sprzętu nie wchodzą do repozytorium. Aby przenieść zapisany projekt, użyj w aplikacji Zapisz, a następnie skopiuj cały folder projektu (project.sqlite wraz z kopiami źródeł). Nie edytuj jednocześnie tej samej bazy projektu na dwóch komputerach. Kod można rozwijać równolegle, bieżący format projektu nie obsługuje współedycji online.

Lokalne przykłady wymienione w README mogą być nieobecne w paczce kodu. Testy tworzą własne syntetyczne PDF; do zwykłej pracy otwórz swój PDF. Test_L3.cmd wymaga osobnego lokalnego przykładu examples/projekt-l3-05.

## Testy

Po instalacji, w katalogu aplikacji: **Testy.cmd**.
Dodatkowo ustaw ELECTROCOUNT_TEST_HALA na ścieżkę PDF hali oraz ELECTROCOUNT_TEST_PACK na folder pakietu testowego. Bez tych plików testy rzeczywistych dokumentów są jawnie pomijane.


## Większy model i oznaczenia elektryczne

Domyślny model to AI Base. W menu Ustawienia → Model analizy możesz wybrać Base, Small albo klasyczny. Small wymaga jednorazowo `Instaluj_AI.cmd --model small`. Po instalacji analiza jest lokalna i nie potrzebuje internetu.

Zaznacz cały symbol wraz z kodem typu i właściwymi oznaczeniami IP, EX lub faz. Program nie zakłada IP20, jeśli oznaczenia nie ma. Brak wymaganej cechy trafia do sprawdzenia; inny jawny wariant jest oddzielany. Zmiana numeru obwodu nie rozdziela tego samego typu urządzenia. Model nie był trenowany na Twoich prywatnych rysunkach.

## Aktualizacja wzorców w 0.7.5

Otwórz projekt w nowym folderze aplikacji i ponownie kliknij Znajdź. Starsze wzorce są odtwarzane w definicji 9, z RGB i kontekstem. Dla nowego wzorca wystarczy zaznaczyć cały symbol; pewne oznaczenie w pobliżu jest pobierane z PDF. Przy zatłoczonym rysunku zaznacz symbol wraz z właściwym oznaczeniem. Sprawdź odczytany numer w panelu przed zliczaniem.

Licznik grupy pokazuje przypisane wyniki. Elementy bez pewnego numeru pozostają osobno jako „Bez przypisania”; inne numery są innymi wariantami. Sama nazwa grupy nie potwierdza poprawności wszystkich wyników.
