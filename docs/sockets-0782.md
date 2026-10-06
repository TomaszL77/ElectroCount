# ElectroCount 0.7.8.2 — obrysy gniazd i nauka wstępna

W niektórych eksportach CAD klip całej strony zawiera kilkanaście współliniowych wierzchołków. Poprzedni odczyt dopuszczał wyłącznie cztery narożniki, przez co odrzucał poprawne ścieżki urządzeń. Teraz upraszcza wielokąt i potwierdza, że zawiera całą geometrię. Faktycznie przecięte symbole pozostają odrzucone. Ramka otaczająca zaznaczenie nie jest jego częścią, jeśli jej namalowane krawędzie go nie przecinają.

Dla rozpoznawalnego kształtu gniazda półkolistego oddzielnie porównywane są pełny korpus i wektorowe oznaczenie. Porównanie obrysów uwzględnia różną liczbę odcinków i skalę legendy, a napis może mieć własny rozmiar lub obrót. Wewnętrzny łuk IP44 pozostaje obowiązkową cechą; odzyskiwanie z tła nie może go usuwać. Oryginalne zaznaczenie i jego wszystkie części pozostają w podglądzie.

Przycisk **Wszystkie typy gniazd** porównuje wzorce grup jednocześnie, wykorzystując jeden skan strony. Wycinki wzorców legendy są pomijane w zliczaniu, ale pozostałe urządzenia na tej samej stronie nadal są wyszukiwane. Dla osobnej strony zawierającej wyłącznie legendę można włączyć Ustawienia → Cała strona wzorca jest legendą. Typ musi wygrać porównanie z pozostałymi wariantami. Zlokalizowane gniazdo o nieczytelnym lub innym oznaczeniu trafia do **Sprawdź**, zamiast znikać. Dla sprawdzonego katalogu projekt może również zapisać rodzinę symboli zamkniętych (np. PEL/HDMI) oraz sieciowych; sama obecność koła lub kwadratu nie czyni wzorca gniazdem. Wyszukiwanie wybranej grupy stosuje bardziej zachowawczy próg oznaczenia.

Mały model ocenia i porządkuje niepewne pary obrazów. Nie zastępuje rozróżnienia typu ani sam nie zatwierdza ilości. **Dodaj wszystkie ze Sprawdź do oceny** nadal zapisuje kolejkę Do oceny; dopiero świadoma ocena staje się przykładem.

## Pierwsza nauka

Gdy brak danych z czterech niezależnych dokumentów, ale w zbiorze Uczenie jest co najmniej 20 poprawnych i 20 błędnych kształtów oraz 30 różnych lokalizacji, przycisk zmienia się na **Wytrenuj wstępnie**. W tym trybie kontrolowane są inne lokalizacje z tych samych PDF-ów. Wszystkie pary z jednego fizycznego wycinka należą do tego samego podziału, także przy różnych wzorcach. Istniejące dokumenty oznaczone Walidacja/Test nie są wykorzystywane do nauki wstępnej.

Raport i model zapisują oznaczenie nauki wstępnej, źródła ocen, identyfikatory przykładów i ograniczenie dotyczące nowych dokumentów. Nie zmienia się podział PDF-ów w bazie. Pełne trenowanie z kontrolą na innych dokumentach działa na dotychczasowych zasadach. Dane oraz model można eksportować i zaimportować na innym komputerze.

Błędny kształt to rzeczywiście inne urządzenie lub element rysunku w porównaniu ze wzorcem. Pominięte poprawne gniazdo należy dodać ręcznie i ocenić jako Poprawny. Inny napis, wariant lub niepewny przypadek pozostaje poza binarną nauką par.

## Sprawdzenie

Dodano sześć skoncentrowanych regresji, w tym legendę osadzoną na stronie schematu: klip z wieloma wierzchołkami, rzeczywiste przecięcie, ramka bez namalowanej krawędzi w wycinku, retesselacja i niezależny rozmiar oznaczenia z ochroną IP44 oraz przenośny model wstępny bez pobierania danych z odłożonego dokumentu. Dotychczasowe aktywne testy przygotowania wzorca, renderowania i uczenia pozostają wymagane.
