# Stan prac — 20.09.2026

Cel: desktopowa aplikacja Windows ElectroCount do zliczania dowolnego wzorca wybranego na dokumentacji instalacji. PySide6, Python 3.12, PDFium, OpenCV. Wersja 0.5.0. GUI i worker są w src/electrocount. Źródłem prawdy jest kod i testy, nie historyczne raporty.

## Działa

Import PDF, drag & drop, wiele grup, wzorzec, zliczanie, weryfikacja, konflikty, ręczne poprawki, undo/redo i zapis/odczyt projektów. FileImportManager kieruje CAD do interfejsu CADEngine, parser DWG/DXF nieaktywny. HardwareProfiler oraz profile AUTO i budżety wydajności działają. AIEngine jest fasadą istniejącej detekcji, nie ciężkim modelem neuronowym.

Natywna geometria PDF jest indeksowana lokalnie i weryfikowana razem z tekstem. Obrót symbolu i etykiety, osobne sygnały kształtu/tekstu/powiązania przestrzennego, raster jako fallback. Nie stosuj OCR, jeśli PDF udostępnia tekst. Nie zamieniaj O/0 ani I/1 w tekście natywnym. Inna etykieta trafia do discoveries, brak pewnej etykiety do nieprzypisanych REVIEW. Detekcja nie jest samym zliczaniem napisów.

## Potwierdzone wyniki

Ostatni pełny lokalny zestaw: 62 testy zaliczone z dostarczonymi dokumentami (historyczny wynik, uruchom ponownie po zmianach). Demo QP14=4 i A1=8.

20.09.2026 ręcznie potwierdzono 72 rzeczywiste oprawy L3 na pierwszej stronie PDF 3525_30_HAL-A_IE_PT_00_201_Instalacja oświetlenia - hala cz.1.pdf: 6 rzędów po 12. Warstwa tekstowa ma 74 napisy L3; pozostałe to oś konstrukcyjna i legenda. SHA256 dokumentu: d3a3158ea0071ed6ea4132fa94ab0761a7dcb119f847466e22194dc749e69a5f.

Następnie wykonano świeże wyszukiwanie przez MainWindow.find_matches i worker aplikacji, próg 0.82, selection_rect=[3153,1389,16,46]. Wynik: 72 przypisane L3, 72 unikalne prawidłowe położenia etykiet, 0 pominiętych, 0 dodatkowych. Czas ok. 15 s z cache. Panel: 0 zaakceptowanych, 72 REVIEW, 0 konfliktów. Dodatkowo 61 bez przypisania i 415 innych etykiet (L5:62, L4:304, L1:48, LITOWO-JONOWYCH:1). Pozostałe typy nie zostały ręcznie potwierdzone.

## Następne zadania

1. Czytelny główny wynik „Znaleziono 72 L3”; oddzielić liczbę wykryć od stanu zatwierdzenia. Zachować weryfikację użytkownika.
2. Poprawić rozpoznawanie etykiet: słowo opisowe LITOWO-JONOWYCH nie powinno być kodem oprawy. Nie ograniczać się do listy znanych nazw; aplikacja ma działać dla nowych wzorców.
3. Ograniczyć szum 61 nieprzypisanych kandydatów, nie ukrywając rzeczywiście niepewnych symboli.
4. Testować różne referencyjne symbole, marginesy zaznaczenia, rozmiary napisów i obroty na nowych PDF. Sukces jednego wzorca nie dowodzi niezawodności całego systemu.
5. Dopiero po ocenie bazowej rozwijać przygotowane interfejsy ModelManager, ContextEngine, TrainingDatasetManager. OCR, ciężki model, legenda i trening nieaktywne. Nie deklarować ich jako działających.

Wcześniejszy problem: identyczna sąsiednia oprawa L3 nie była wykrywana. Oba sąsiednie symbole są obecnie odnajdywane. Panel postępu zmniejszono do ok. 60 px. Projekt v2 zachowuje kompatybilność ze starszymi projektami. Nie zamykać cudzej uruchomionej aplikacji z niezapisanym projektem.
