# ElectroCount 0.7.2 — wyszukiwanie wskazanego wzorca

Lokalna aplikacja Windows do zliczania konkretnego symbolu wybranego na rzucie albo w legendzie. Wzorzec łączy geometrię, kolor, oznaczenie i jego otoczenie. Program nie klasyfikuje automatycznie wszystkich instalacji.

0.7.2 poprawia zgodność symboli z podzielonymi odcinkami w PDF oraz analizę obrazową symboli przeciętych linią biegnącą poza wzorcem. Panel pokazuje wyraźny licznik znalezionych i filtr aktywnej grupy. [Zmiany i zakres testów](docs/detection-072.md).

## Uruchomienie

Python 3.12 64-bit → **Instaluj.cmd** → **Uruchom.cmd**. Instalator pobiera przypięte biblioteki i lokalny model DINOv2-small (89 MB), sprawdza SHA-256, uruchamia test modeli i test kontrolny 12/12. Runtime znajduje się w `%LOCALAPPDATA%/ElectroCount/py312-07`. Inference działa bez internetu. Na drugim komputerze wykonaj osobną instalację; nie kopiuj `.runtime-path` ani środowiska Python.

[Instrukcja pracy na dwóch komputerach](START-TUTAJ.md) · [Stan prac](CONTINUE.md) · [Trudne symbole CAD — 0.7.1](docs/cpp203-071.md) · [Architektura 0.7](docs/one-shot-07.md)

Wersja 0.7.1 rozróżnia puste i wypełnione środki symboli, lepiej oddziela oprawę od przewodów i tła oraz wyłącza przykłady z legend i rozpoznanych ramek uwag. Na CPP-TD-CR-EB-203 aplikacja wykrywa 113 L1 i 76 L1-1. Są to wyniki detektora, wymagające weryfikacji; nie stanowią potwierdzenia kompletnej liczby opraw.

## Jak zliczać

1. Otwórz PDF i zaznacz pojedynczy symbol razem z oznaczeniem.
2. Odczytane oznaczenie zostanie nazwą grupy. Bez oznaczenia powstaje Symbol 01, Symbol 02 itd.
3. Kliknij **Znajdź**. Domyślnie analizowane są wszystkie strony wszystkich dokumentów projektu. Opcja „Tylko bieżąca strona” ogranicza zakres.
4. Zweryfikuj oznaczone wyniki. Pomarańczowe elementy wymagają oceny; inne oznaczenia urządzeń nie trafiają automatycznie do aktywnej grupy.
5. Dla legend bez rozpoznawalnej ramki użyj **Ustawienia → Wzorzec pochodzi z legendy**, następnie ponów wyszukiwanie. Źródło z legendy nie zwiększa ilości. Wzorzec wybrany na rzucie pozostaje rzeczywistym urządzeniem i jest liczony.

L3 na zweryfikowanej hali: **72 oprawy + 1 odniesienie w legendzie**. QP14/A1 w dostarczonym przykładzie: **4 / 8**. To wyniki konkretnych testów, a nie gwarancja dla każdego rysunku.

## Jedna jakość na każdym PC

Nie ma profili ECO / STANDARD / ENHANCED / MAXIMUM. HardwareProfiler pozostaje wyłącznie narzędziem diagnostycznym, nie wybiera silnika ani progów. Analiza korzysta z CPU, stałych modeli, skali i reguł. Po braku pamięci zmniejszany jest wyłącznie cache. Niepełna operacja nie publikuje częściowych ilości jako pełnego wyniku.

## Klasyczny i hybrydowy silnik

**Domyślny pozostaje poprawiony silnik klasyczny.** Uwzględnia natywną geometrię PDF, ORB/RANSAC i kontury dla rastra, dokładny tekst, role adnotacji i rozkład koloru. Oznaczenia EW1/EW2 nie są utożsamiane; odwołania TP04/47 i TP04/52 nie rozdzielają urządzenia na typy.

**Ustawienia → Hybryda DINOv2 — porównanie eksperymentalne** dodaje embedding FP32 i niezależne przeszukanie całej strony kafelkami. Model zobaczy również regiony pominięte przez klasyczny generator. Kandydaci są scalani, a potem weryfikowani geometrią i tekstem. Lokalny PP-OCRv4 jest fallbackiem dla regionów bez natywnego oznaczenia; nigdy nie zastępuje dostępnego kodu PDF. Brak modelu powoduje jawny błąd, a nie ciche wyłączenie AI na słabszym PC.

Hybryda musi wykazać przewagę precision i recall bez regresji, zanim stanie się domyślna. Nie ma treningu własnego modelu, automatycznego zbierania danych ani wysyłania rysunków do sieci. DINOv2 nie jest specjalistycznym modelem symboli elektrycznych. SuperPoint/LightGlue pozostają interfejsem opcjonalnym; aktywny lokalny matcher korzysta z ORB/RANSAC i analizy konturów.

## Diagnostyka i testy

**Ustawienia → Detection Debug** pokazuje osobno wyniki geometrii, cech lokalnych, koloru, embeddingu, tekstu i położenia oraz powód decyzji. `null` oznacza brak użytego sygnału. **Tryb diagnostyczny: zapisuj wycinki** zapisuje wejścia i logi lokalnie. **Diagnostyka.cmd** uruchamia self-test 12/12. **Testy.cmd** uruchamia regresje.

Testy rzeczywistych dokumentów wymagają `ELECTROCOUNT_TEST_HALA` i `ELECTROCOUNT_TEST_PACK`. Bez plików są jawnie pomijane. Benchmark parowany: `python tools/benchmark_retrieval.py --output <folder> --hall <PDF_hali>`. Zawiera metryki precision, recall, F1, FP, FN z dopasowaniem lokalizacji 1:1; sama zgodność ilości nie wystarcza.

DWG/DXF nadal korzystają z interfejsu CADEngine; nie dodano prowizorycznego parsera DWG. Nie ma jeszcze samodzielnego EXE.
