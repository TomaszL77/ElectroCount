# ElectroCount 0.5 — detekcja i walidacja, 19.09.2026

## Wdrożone zmiany

`native_geometry.py` indeksuje położenia, rozmiary i charakter koloru ścieżek. Szczegółową geometrię odczytuje dopiero w lokalnym zapytaniu. Limit pełnego rysunku nie usuwa już możliwości porównania małego symbolu. Indeks zajmuje 56 bajtów na ścieżkę plus obsługę zagnieżdżonych obiektów; to nie jest pomiar całej pamięci PDFium.

Wzorzec ma oddzielny prostokąt zaznaczenia, właściwą geometrię, obszar tekstu, układ oznaczenia i prostokąt pomocniczy dla rastra. Cienkie wypełnione korpusy można oddzielić od przewodów i nakładających się napisów. Przy wyraźnym kolorze wybierana jest geometria pierwszego planu zamiast tysięcy szarych kresek tła. Kolor sam nie zatwierdza wykrycia. Podgląd pokazuje rzeczywiście wyodrębniony kształt.

Dopasowanie obejmuje całe segmenty i ich układ, obroty oraz skalę 0,8–1,25. Nie wystarcza pasujący fragment dłuższej oprawy. Obrót przenosi również oczekiwane położenie etykiety. Warianty rastra o różnych skalach i orientacjach pozostają dostępne do weryfikacji; najwyższy wynik bitmapy nie usuwa przedwcześnie pozostałych wariantów. Obroty rastrowe 90/180/270 stopni nie wprowadzają interpolacji.

Dokładne wystąpienia kodu priorytetyzują pobliskie hipotezy wektorowe. To nie jest niezależne zliczanie samych napisów. Indeks tekstu przyspiesza przypisywanie etykiet. Powtórzony identyczny tekst PDF nie tworzy sztucznej niejednoznaczności. Jednostki takie jak 117W są traktowane jako opis. Rozmiar pisma jest wskazówką, nie sztywnym warunkiem — mniejsze oznaczenie obok identycznej oprawy pozostaje dopuszczalne.

Nowy indeks można ponownie otworzyć w następnym procesie aplikacji: cache zawiera stabilne numery obiektów, nigdy wskaźniki natywne. Zmiana źródła unieważnia cache. Indeksy stron z zagnieżdżonymi ścieżkami Form są obecnie budowane ponownie. Cache dyskowy pozostaje ograniczony do 256 MB. Rzeczywiście przycięte symbole i przekroczone limity zachowują drogę rastrową; częściowa geometria nie jest przedstawiana jako pełna. W przypadku niepowodzenia uzupełniającej analizy obrazu wynik zawiera ostrzeżenie.

`template_preview.py` dodaje podgląd przy grupie. Panel ładowania ma około 60 px wysokości zamiast około 105 px. Zachowuje etap, stronę, procent, czas i anulowanie. Znaczniki bardzo cienkich obiektów mają minimalną widoczną szerokość; dokładne prostokąty pomiarowe pozostają niezmienione.

Fasada `AIEngine` używa DetectionEngine V3 i zapisuje osobne sygnały geometrii, cech, tekstu i powiązania. Enkoder neuronowy, OCR, model legendy, ContextEngine i trening pozostają nieaktywne. Dokumenty nie są przesyłane do usług zewnętrznych.

## Wyniki

- **62 testy przeszły, 0 błędów i 0 pominiętych, 169,85 s**. Włączono oba lokalne testy: cztery pliki pakietu oraz halę. Wynik: `test-results.xml`.
- Po ostatniej kosmetycznej zmianie znaczników ponownie przeszły oba testy GUI (2/2, 9,12 s) oraz otwarcie i zapis hali.
- Test niewidzianego wcześniej złożonego symbolu: cztery orientacje znalezione zarówno drogą natywną, jak i rastrową. Odrzucono niekompletny kształt i sam kod bez urządzenia. Ten sam kształt z innym kodem pozostał osobnym odkryciem.
- Kontrole obejmują cienkie korpusy, dłuższy mylący korpus, szare tło, różne wielkości pisma, duplikaty tekstu, zagnieżdżone Form, przycięcie, ponowne otwarcie cache, zmianę źródła i aktualizację starego wzorca.
- Demo zachowuje **QP14=4, A1=8**. Sprawdzono też grupy, konflikty, Undo/Redo, anulowanie, zapis/odczyt i profile sprzętu.
- Hala: oba sąsiednie L3 znalezione z obu egzemplarzy jako wzorca i przy trzech marginesach. Dla całej strony algorytm zwrócił **72 kandydatów L3**, 61 podobnych obiektów bez przypisania oraz 415 obiektów z innymi oznaczeniami. Trzy przygotowania wzorca i analiza z cache zajęły 26.25 s. Indeks 111,954 ścieżek zajmuje 5.98 MiB.
- E-01: wybrany pomarańczowy symbol PEL został wyodrębniony ze złożonego szarego tła. Algorytm zwrócił **61 zgodnych kształtów**, w tym wskazany egzemplarz. Nie odczytał kodu — tekst tego PDF jest grafiką. Budowa indeksu: 32.25 s; analiza z gotowym indeksem: 39.14 s. Indeks 449,185 ścieżek zajmuje 23.99 MiB.

Liczby 72 i 61 są wynikami algorytmu, **nie ręcznie potwierdzonym zestawieniem ilościowym**. Nie wyliczamy precision/recall bez adnotacji całej strony. Kontrolowana para z hali jest odtwarzalnym wycinkiem; nie odtworzono dokładnego, niezapisanego zaznaczenia z okna użytkownika. Czasy dotyczą tego komputera i konkretnego przebiegu, nie gwarancji dla dowolnego pliku.

## Sprawdzenie aplikacji

Uruchomiono osobną instancję testową GUI. PDF hali otworzył się, podgląd wzorca był widoczny, grupa L3 miała 72 pozycje do sprawdzenia. Zapis przez GUI i ponowny odczyt zachowały wyniki. Błędy workerów: 0. Wcześniej otwarta instancja użytkownika nie była zamykana. Dowody: `uruchomienie-05.json`, `podglad-l3-05.png`, `podglad-postepu.png`.

Projekt do obejrzenia: `examples/projekt-l3-05/project.sqlite`. Otwiera się na dwóch sąsiednich L3 i zawiera kopię źródłowego PDF. Automatyczne trafienia nie zostały oznaczone jako ręcznie zatwierdzone.

## Kolejny etap i granice

Nadal potrzebny jest zestaw ręcznie oznaczonych przykładów z różnych projektów, OCR tylko tam, gdzie nie ma tekstu natywnego, oraz wykluczanie legend i tabel. Segmentacja nie ma jeszcze edytora maski ani mechanizmu uczenia z drugiego przykładu. Sama geometria nie rozstrzygnie dwóch identycznych symboli pozbawionych czytelnego kodu. Kolejny model należy porównywać z tą bazą na nowych dokumentach, zanim zacznie wpływać na ilości.

Klipy i ścieżki są obsługiwane przez natywne API PDFium; dokumentacja: https://pdfium.googlesource.com/pdfium/+/refs/heads/main/public/fpdf_edit.h. Szczegółowe raporty lokalnych prób: `regresja-l3-05.json` i `regresja-e01-05.json`.
