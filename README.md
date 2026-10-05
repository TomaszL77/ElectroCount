# ElectroCount 0.7.7.2 — szybkie, ostre wyświetlanie schematów

Podstawa: 0.7.7.1, commit `2ebe006d6421872d5d52cc249bdcd463d51acd14`. Schemat jest renderowany kafelkami w osobnym, stałym procesie PDFium. Widok zapamiętuje ostre fragmenty i doczytuje sąsiednie; przeciąganie uruchamia renderowanie podczas ruchu. Rozdzielczość uwzględnia powiększenie i DPI monitora.

Dokładny prostokąt użytkownika pozostaje zachowany w `selection_bbox`, oryginalnym RGB i podglądzie. Nieudany test rozpoznawania nie blokuje jego zapisu. Poprawka renderowania nie zmienia detektora ani zliczeń; panel uczenia nie został jeszcze dodany.

Uruchom **Uruchom.cmd z folderu tej wersji**. Tytuł okna musi zawierać **0.7.7.2**. Biblioteki/runtime 0.7 pozostają zgodne. Przy pierwszej instalacji lub brakujących bibliotekach użyj Instaluj.cmd. Stary skrót pulpitu może prowadzić do innego folderu.

Do próby ręcznej otwórz swój PDF, powiększ drobne oznaczenia i przesuwaj widok, także tam i z powrotem. Sprawdź zmianę stron i zaznaczenie wzorca. Zupełnie nowy obszar może przez chwilę korzystać z podglądu; nie trzeba już zatrzymywać przeciągania, aby rozpocząć doczytywanie jakości.

**Testy.cmd uruchamia 15 małych kontroli renderowania i wzorca.** Wynik: 15 PASS. Na świeżym syntetycznym rysunku mediana czasu tego samego fragmentu 512×512 px spadła z 250 ms do 18 ms w tym środowisku Linux. Nie jest to pomiar na komputerze użytkownika ani czas całej analizy.

Diagnostyka wzorca zapisuje wyłącznie `selection_crop.png`, `matching_crop.png` i krótki `template_log.json`. Dawne zestawy wyników i zatwierdzone pliki testowe usunięto z tej gałęzi; cache ma nową przestrzeń nazw.

[Raport renderowania](docs/render-0772.md) · [Wzorzec](docs/template-077.md) · [Dalsza praca](CONTINUE.md) · [Drugi komputer](START-TUTAJ.md)
