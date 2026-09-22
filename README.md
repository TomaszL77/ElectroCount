# ElectroCount 0.6 — powtarzalna instalacja i diagnostyka

Lokalna aplikacja Windows do zliczania symboli instalacji. Nowy silnik wyodrębnia lokalną geometrię wzorca, sprawdza obroty i wiąże wyniki z dokładnym tekstem PDF. Zachowuje HardwareProfiler, AUTO, grupy i format projektu. Nie instaluje modeli ani nie uruchamia treningu.

## Uruchomienie

Na każdym komputerze: Python 3.12 64-bit → **Instaluj.cmd** → **Uruchom.cmd**. Instalator sprawdza wersje i SHA-256 bibliotek oraz wynik wbudowanego testu 12/12. Runtime znajduje się w krótkiej ścieżce `%LOCALAPPDATA%/ElectroCount/py312-06`, aby uniknąć błędu długich ścieżek PySide6 na Windows.

**Zacznij od [START-TUTAJ.md](START-TUTAJ.md)**. Stan prac: [CONTINUE.md](CONTINUE.md). Opis przyczyn błędu 1/72, zbierania wycinków i testów: [docs/diagnostyka-06.md](docs/diagnostyka-06.md).

Wersja 0.6 naprawia wybór pojedynczej oprawy z większego zaznaczenia, odrzuca przecięte korpusy i zapisuje współrzędne gestu. GUI, CLI i self-test używają tego samego `run_detection`. W PDF hali wynik to 73 symbole L3 razem z legendą, 1 przykład wyłączony, 72 sztuki. Legenda jest rozpoznawana konserwatywnie z nagłówka i ramki tabeli. Wyniki mają wyraźny obrys niezależny od zoomu. Ustawienia → Tryb diagnostyczny zapisuje wycinki i log analizy. Diagnostyka.cmd uruchamia kontrolę instalacji. Nie ma jeszcze packaged EXE.

Przykład kontrolny: `examples/projekt-ai-demo/project.sqlite`. Szybkie otwarcie przykładu: **Test_L3.cmd**. Rzeczywista hala z grupą L3 i widokiem kontrolowanej pary: **examples/projekt-l3-05/project.sqlite**. Wszystkie automatyczne wyniki w tym projekcie wymagają weryfikacji.
Test kontrolny na `rzut-testowy-demo.pdf`, strona 1: **QP14 = 4, A1 = 8**. Wyniki automatyczne oczekują weryfikacji użytkownika.

## Wydajność

W menu **Ustawienia → Wydajność i sprzęt** lub przyciskiem na dolnym pasku wybierz AUTO, Eco, Standard, Enhanced albo Maximum. Ustawienie jest zachowywane lokalnie i działa dla kolejnych operacji.

AUTO sprawdza CPU, rdzenie, wolny/całkowity RAM, adaptery GPU, pamięć raportowaną przez DXGI, DirectX 12, runtime Windows ML, sterownik CUDA oraz zainstalowane backendy. Następnie mierzy renderowanie syntetycznego PDF i ekstrakcję ORB. Profilowanie działa w oddzielnym procesie; limit startowy wynosi 15 sekund, a aplikacja pozostaje dostępna.

Brak zainstalowanego enkodera i adaptera GPU oznacza **pomiar inference pominięty**, a nie wynik zerowy ani deklarowaną akcelerację. GPU wykryte w komputerze nie jest automatycznie aktywnym backendem AI.

W etapie 1 AUTO wybiera Eco lub Standard. Enhanced/Maximum można wymusić jako budżety zasobów; nie włączają nieistniejących modeli. Profile zmieniają liczbę wątków OpenCV i wielkość cache, zachowując kryteria tekstowe i geometryczne. Dostępna pamięć jest odczytywana ponownie przy uruchomieniu. Wyniki benchmarku są ważne do 7 dni i unieważniane zmianą wykrytego sprzętu/runtime; przycisk „Zmierz ponownie” wymusza nowy pomiar.

Po błędzie alokacji/obsługiwanym błędzie backendu operacja może zostać ponowiona poziom niżej, z komunikatem. Nie publikuje częściowego wyniku. Jeśli zabraknie zasobów także w Eco, zadanie zgłasza błąd, a projekt pozostaje bez zmian. Awaria procesu roboczego nie zamyka GUI.

## Praca z PDF

1. Otwórz PDF lub przeciągnij pliki z Eksploratora. Obsługiwany jest import wielu dokumentów.
2. Wybierz **Wzorzec** i zaznacz symbol z oznaczeniem.
3. Wiarygodny tekst natywny nada grupie nazwę, np. QP14. Bez oznaczenia powstaje Symbol 01, Symbol 02 itd. Nie pojawia się pytanie o nazwę. Kolejny wzorzec tworzy kolejną grupę, jeśli aktywna ma już wzorzec/wyniki.
4. **Znajdź** domyślnie analizuje wszystkie strony aktualnego dokumentu PDF. Opcja „Tylko bieżąca strona” ogranicza zakres. Pozostałe zaimportowane pliki wybiera się przez ich strony.
5. Sprawdź, zaakceptuj lub odrzuć wyniki. Użyj Detection Debug do inspekcji sygnałów.
6. Zapisz projekt. Folder zawiera project.sqlite i sprawdzone sumami SHA-256 kopie dokumentów.

Lewy i prawy panel można zwijać. Dla pojedynczej strony panel stron domyślnie jest zwinięty; ręcznie zapisany wybór ma pierwszeństwo.

Tekst PDF jest odczytywany bez OCR, z bounding boxami w punktach widocznej strony. Kody porównujemy dokładnie po normalizacji wielkości liter/spacji, bez zamiany O/0 i I/1. A1, A11, A1.1 i AI są odrębne. Nakładające się obiekty tekstowe nie są sklejane w jeden kod.

Wektorowa geometria lub raster generują kandydatów. Raster przechodzi osobną weryfikację cech i geometrii; samo podobieństwo bitmapy nie wystarcza. Kandydat z innym kodem trafia do odkrytych innych oznaczeń. Brak/niejednoznaczny kod przy grupie z etykietą oznacza REVIEW bez przypisania. Grupa bez etykiety służy weryfikacji podobnych kształtów. Wynik łączny jest heurystyką, nie prawdopodobieństwem.

Duży PDF otrzymuje lekki indeks położeń obiektów. Szczegółowe segmenty są odczytywane wokół wzorca i kandydatów, z limitem 40 000 na odczyt. Indeks ma limit miliona ścieżek; ograniczenie lub istotne przycięcie uruchamia dodatkową analizę obrazu. Indeksy prostych stron są zapisywane lokalnie z numerami obiektów, bez wskaźników procesu, i unieważniane po zmianie źródła. Łączny cache ma limit 256 MB. Analizę można anulować.

## Grupy i kompatybilność

Działają kolory, widoczność, akceptacja/odrzucenie, dodawanie ręczne, konflikty, Undo/Redo, ponowna analiza oraz zapis/odczyt. Ukryta grupa nadal uczestniczy w kontroli konfliktów. Automatyczne wykrycia mają domyślnie status do sprawdzenia. Ręczne decyzje są zachowywane przy ponownej analizie potwierdzającej ten sam element.

Starsze wzorce z zapisanym prostokątem zaznaczenia są ponownie wyodrębniane przy wyszukiwaniu. Nazwa grupy i strona projektu są zachowane. Format projektu pozostaje v2; projekty v1 są nadal odczytywane z migracją starych automatycznych wyników do weryfikacji. Nowe pola mają wartości domyślne przy odczycie istniejącego projektu. Profil sprzętu i ustawienia użytkownika są oddzielone od projektu.

DWG/DXF są kierowane przez FileImportManager do interfejsu CADEngine. Parser CAD pozostaje nieaktywny i pokazuje stosowny komunikat. Nie ma prowizorycznego parsera DWG.

## Przygotowane moduły AI

- `hardware_profiler.py`, `hardware_windows.py`: rzeczywiste lokalne odczyty i benchmark.
- `performance.py`, `profiling_service.py`, `performance_dialog.py`, `runtime_runner.py`: profile, ustawienia, proces profilowania i ograniczone ponowienia.
- `ai/contracts.py`: wspólne sygnały, DocumentEntity, relacje i interfejsy dostawców/enkodera/matchera/reasonera.
- `ai/model_manager.py`: lokalny katalog manifestów, wersje, wymagania RAM/VRAM, backendy, SHA-256, kontrola ścieżek. Nie ładuje i nie pobiera modeli.
- `ai/engine.py`: używana przez worker fasada aktualnego DetectionEngine, z pełnym rozróżnieniem aktywnych i nieaktywnych sygnałów.
- `ai/context_engine.py`: neutralny, nieaktywny ContextEngine.
- `ai/training_dataset.py`: kontrakty wersjonowanych przykładów i podziałów; zbieranie danych jest wyłączone.

DINOv2, OCR, kontekstowy VLM, semantyczne rozumienie dowolnej legendy, budowanie grafu, eksport datasetu i trening **nie są aktywne**. Istniejący adapter LightGlue wymaga w przyszłości dostarczenia lokalnie załadowanego modelu; nie instaluje wag. Dokumenty/cropy nie są wysyłane do internetu.

## Testy i dalszy etap

Szczegóły: **docs/testy.md**, **docs/architektura-ai.md**, **docs/pakiet-testowy.json**.

Uruchom **Testy.cmd** lub `python -m pytest -q` w środowisku aplikacji. Dodatkowy test czterech rzeczywistych PDF wymaga ustawienia `ELECTROCOUNT_TEST_PACK` na lokalny folder użytkownika; bez niego jest jawnie pomijany. Test pary z hali używa `ELECTROCOUNT_TEST_HALA` wskazującego dostarczony plik oświetlenia. Pliki pakietu nie są włączone do datasetu treningowego.

Następny etap: uporządkować typy dokumentów i kontekst strony, zbudować graf oraz model legendy, przygotować ręcznie zweryfikowany benchmark. E-01/E-07 wymagają także osobnego OCR fallback, bo widoczne napisy są grafiką, nie tekstem PDF. Dopiero potem mały, lokalny proof of concept enkodera i pomiar jakości na wydzielonym benchmarku.

Logi: logs/electrocount.log. Ustawienia: .state/settings.ini. Zależności pozostają w requirements-lock.txt; bez nowych ciężkich bibliotek.


## Zmiany w wersji 0.5

- Mniejszy panel postępu nad rysunkiem: etap, czas, procent i anulowanie w około 60 px wysokości.
- Podgląd wyodrębnionego wzorca wektorowego przy grupie.
- Cienkie wypełnione korpusy są oddzielane od przewodów; kolor pomaga oddzielić symbol od szarego tła, ale każdy wynik nadal wymaga pełnej geometrii.
- Obsługa obróconych symboli i obróconego położenia oznaczenia. Raster uwzględnia także 90/180/270 stopni bez dodatkowego rozmycia.
- Alternatywne pozy rastra są weryfikowane przed ostatecznym usunięciem duplikatów.
- Dokładne napisy priorytetyzują okolice do sprawdzenia. Same napisy nie są zliczane. Duplikaty tekstu i jednostki mocy nie udają odrębnych kodów.
- Brak kodu w grupie z oznaczeniem nadal oznacza brak przypisania. Inne kody pozostają osobną listą.

W kontrolowanej parze L3 oba elementy są wykrywane z obu wzorców przy trzech marginesach. Demo zachowuje QP14=4/A1=8. To nie jest deklaracja bezbłędności całego rysunku. Nie wdrożono jeszcze automatycznego wykluczania legend, edytora maski, OCR ani uczonego enkodera.

Po zapisaniu otwartego projektu uruchom aplikację ponownie przez **Uruchom.cmd**. Aktualna wersja pokazuje **ElectroCount 0.5** w tytule okna. Szczegóły zmian i pomiarów: **docs/detekcja-05.md**.
