# ElectroCount — drugi komputer

Kod i testy ElectroCount 0.5.0. Windows, Python 3.12 64-bit.

1. Zaloguj się do GitHuba na swoje konto. W GitHub Desktop wybierz File → Clone repository i repozytorium ElectroCount. Jeśli korzystasz z paczki ZIP, najpierw rozpakuj cały folder do lokalnego katalogu.
2. Zainstaluj Python 3.12 64-bit z python.org wraz z Python Launcher. Sprawdzenie: `py -3.12 --version`.
3. Otwórz folder aplikacji i uruchom Instaluj.cmd. Potrzebny jest internet do pobrania bibliotek.
4. Uruchom Uruchom.cmd. Otwórz lokalny PDF. Profil AUTO zmierzy sprzęt tego komputera.
5. W swoim narzędziu do pracy z kodem otwórz ten sam lokalny folder. Przeczytaj CONTINUE.md — opisuje dotychczasowe prace i następne kroki.

## Praca na dwóch komputerach

GitHub przechowuje kod i historię zmian. Każdy komputer ma własny lokalny folder oraz własne środowisko .venv. Nie umieszczaj aktywnego repozytorium w folderze synchronizowanym przez Google Drive.

Przed pracą w GitHub Desktop: Fetch origin → Pull origin. Utwórz osobną gałąź dla zadania, np. dom/panel-wynikow albo praca/detekcja-etykiet. Po pracy: zapisz zmiany jako commit, następnie Publish branch / Push origin. Zmiany łącz przez pull request do main. Przed połączeniem uruchom testy. Dwa komputery mogą pracować równocześnie na osobnych gałęziach; zmiany w tym samym miejscu mogą wymagać rozwiązania konfliktu. Samo zapisanie pliku nie wysyła go na GitHub.

Paczka ZIP na Dysku Google jest kopią zapasową, nie automatyczną synchronizacją kodu. Po skonfigurowaniu repozytorium pracuj z jego klonami.

## Dokumenty i projekty

Rzeczywiste PDF/DWG/DXF, zapisane projekty, cache, modele i ustawienia sprzętu nie wchodzą do repozytorium. Aby przenieść zapisany projekt, użyj w aplikacji Zapisz, a następnie skopiuj cały folder projektu (project.sqlite wraz z kopiami źródeł). Nie edytuj jednocześnie tej samej bazy projektu na dwóch komputerach. Kod można rozwijać równolegle, bieżący format projektu nie obsługuje współedycji online.

Lokalne przykłady wymienione w README mogą być nieobecne w paczce kodu. Testy tworzą własne syntetyczne PDF; do zwykłej pracy otwórz swój PDF. Test_L3.cmd wymaga osobnego lokalnego przykładu examples/projekt-l3-05.

## Testy

Po instalacji, w katalogu aplikacji: `.venv\Scripts\python.exe -m pytest -q`.
Dodatkowo ustaw ELECTROCOUNT_TEST_HALA na ścieżkę PDF hali oraz ELECTROCOUNT_TEST_PACK na folder pakietu testowego. Bez tych plików testy rzeczywistych dokumentów są jawnie pomijane.
