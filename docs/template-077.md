# 0.7.7 — etap 1, 3 października 2026

## Przyczyna

`NativeVectorPage.template_signature` zawężał ścieżki do kolorowych, pojedynczego wypełnionego rdzenia albo usuwał elementy uznane za przewody. Dalsze `signature()` usuwało końcówki i nadmiarowe kontury. `prepare_template` zastępował prostokąt zaznaczenia granicami tej geometrii albo ciasnym wycinkiem rastra. `build_representation` renderował oryginał RGB z `raster_rect`, a podgląd wyświetlał ten już zmieniony obraz. Dotychczasowe `self_check=bool(signature)` potwierdzało tylko istnienie geometrii, nie rozpoznanie źródła.

## Poprawka

`selection_bbox` jest kopią dokładnego zaznaczenia i nigdy nie jest zastępowany granicami geometrii. Oryginalny RGB i podgląd używają tego prostokąta. `symbol_bbox` jest opcjonalnym opisem geometrii, `matching_bbox` obszarem obrazu do porównania, `context_bbox` otoczeniem tekstu. Stare klucze pozostają dla zgodności projektu, ale nie sterują oryginalnym wycinkiem.

Wyłączono filtrowanie kolorów, wybór samego rdzenia, usuwanie ścieżek kontekstu i końcówek podczas przygotowania wzorca. Zachowano wszystkie wybrane ścieżki, wypełnienia i kolory. Przy przeciętych obiektach, obrazie albo ograniczeniu ekstrakcji pozostaje pełny raster zaznaczenia; nie wybieramy tylko ocalałych fragmentów geometrii. Tekst może być maskowany w obrazie pomocniczym, ale pozostaje w oryginale i w analizie oznaczenia.

Lokalny self-match wyszukuje źródło istniejącym generatorem i weryfikatorem, bez dopisywania sztucznego trafienia. Niepowodzenie blokuje utworzenie wzorca i zgłasza błąd. To kontrola miejsca źródłowego, nie pomiar recall całej dokumentacji. Definicja wzorca 11 wymusza odtworzenie starego wzorca z zachowanego zaznaczenia przy wyszukiwaniu.

Diagnostyka zapisuje tylko dwa obrazy (`selection_crop.png`, `matching_crop.png`) i `template_log.json` z polami selection_bbox, symbol_bbox, matching_bbox, source, extraction_mode, detected_label, preserved_paths, removed_paths. Dla pełnego rastra liczba zachowanych ścieżek jest nieustalona (`null`); usuniętych części jest 0. Wyłączono utrwalanie wielkich raportów detekcji i wycinków kandydatów.

## Pięć kontroli

Każdy test tworzy własny mały, świeży dokument w katalogu tymczasowym. Nie korzysta ze starego PDF, cache, wzorca ani listy trafień.

| Kontrola | Wynik |
|---|---|
| 1. Wieloelementowy symbol i niezależna kopia zaznaczenia | PASS — wszystkie trzy ścieżki zachowane, napis 7 odczytany |
| 2. Magenta + czarna kreska i koło | PASS — obie barwy i wszystkie części zachowane |
| 3. Filled core + obrys i koło | PASS — pełny symbol, bez redukcji do rdzenia |
| 4. RGB i podgląd = selection_bbox | PASS — pikselowa zgodność z renderem 100 × 80 pt; również self-match rastrowy |
| 5. Self-match i kontrola błędu | PASS — rzeczywisty detektor znajduje źródło w legendzie; brak lokalnego trafienia zgłasza błąd tworzenia |

Pierwsze uruchomienie: 5 PASS, 10,97 s. Po drobnej korekcie diagnostyki i integracji fallbacku ponowiono wyłącznie kontrole 4–5: 2 PASS, 3,23 s. Pełnej regresji ani dawnych benchmarków nie uruchamiano.

## Pliki implementacji

- `text_engine.py`, `native_geometry.py`, `vector_engine.py`: zachowanie zaznaczenia i kompletu wybranej geometrii; weryfikator respektuje ten komplet.
- `template_representation.py`, `template_preview.py`: dokładny RGB i podgląd; rozdzielone prostokąty.
- `template_self_match.py` (nowy), `detection_service.py`, `detection_engine.py`: kontrola źródła, migracja definicji i minimalna diagnostyka.
- `diagnostics.py`, `pdf_cache.py`: dwa wycinki i krótki JSON; nowa przestrzeń cache wyklucza stare dane.
- `__init__.py`, `pyproject.toml`: wersja 0.7.7 i domyślnie tylko pięć kontroli.
- `tests/test_template_077.py` (nowy), cztery pliki dawnych testów prywatnych: świeże kontrole i usunięcie przypadków wymagających konkretnych prywatnych dokumentów.
- `README.md`, `CONTINUE.md`, `START-TUTAJ.md`, `.gitignore` i ten raport: instrukcja bieżącego etapu.

## Porządki

Usunięto 9 plików zapisanych wyników z docs/benchmarks-076, 2 dawne PDF-y z tests/fixtures, benchmark_cpp203.py, benchmark_documents_076.py, benchmark_retrieval.py, verify_gui.py oraz Test_L3.cmd. Te dokładne usunięcia użytkownik dodatkowo zatwierdził po blokadzie automatycznej kontroli. Pozostałe ogólne testy zachowano, lecz nie są zestawem etapu 1. Archiwalne opisy w docs nie są wejściem algorytmu ani dowodem poprawności 0.7.7.

Kopia robocza powstała z czystej wersji 0.7.6, bez starych lokalnych projektów i cache. Nie naruszono oryginalnej kopii na pulpicie ani prywatnych dokumentów. Main pozostaje bez zmian.

## Zatrzymanie

Wyłącznie etap 1. Nie zmieniano modeli, progów dla CPP, sposobu generowania kandydatów ani układu GUI. Dalsze prace dopiero po ręcznej ocenie użytkownika.
