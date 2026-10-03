# ElectroCount 0.7.7 — etap 1: poprawne zaznaczenie wzorca

Podstawa: gałąź `feature/detection-0.7.6`. Ta wersja naprawia wyłącznie przygotowanie wzorca. Dokładny prostokąt użytkownika zostaje zachowany w `selection_bbox`, oryginalnym RGB i podglądzie. Czarne części, inne kolory, końcówki i dodatki do wypełnionego rdzenia nie są automatycznie usuwane.

`symbol_bbox` opisuje opcjonalną geometrię, `matching_bbox` obszar obrazu dla matchera, a `context_bbox` otoczenie do analizy tekstu. Nie zastępują zaznaczenia. Napisy mogą być analizowane osobno. Po przygotowaniu odbywa się lokalny self-match; jego niepowodzenie jest błędem tworzenia wzorca, a nie niską pewnością.

Uruchom **Uruchom.cmd z folderu tej wersji**. Tytuł okna musi zawierać **0.7.7**. Wymagane są dotychczasowe biblioteki/runtime 0.7; nie zmieniono modeli AI ani ich instalacji. Przy pierwszej instalacji użyj Instaluj.cmd. Stary skrót pulpitu może prowadzić do innego folderu.

Do próby ręcznej wybierz nowy wzorzec z legendy. Po zapisaniu projektu można wrócić do poprzedniej wersji z osobnego folderu.

**Testy.cmd uruchamia tylko pięć małych kontroli etapu 1.** Wszystkie zaliczone; self-match odnalazł element źródłowy. Nie uruchamiano pełnej regresji ani benchmarków prywatnych dokumentacji. Dawne wyniki nie są dowodem poprawności tej wersji.

Diagnostyka wzorca zapisuje wyłącznie `selection_crop.png`, `matching_crop.png` i krótki `template_log.json`. Dawne zestawy wyników i zatwierdzone pliki testowe usunięto z tej gałęzi; cache ma nową przestrzeń nazw.

[Raport etapu 1](docs/template-077.md) · [Dalsza praca](CONTINUE.md) · [Drugi komputer](START-TUTAJ.md)
