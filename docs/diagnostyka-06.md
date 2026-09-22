# ElectroCount 0.6 — diagnostyka różnic między komputerami

## Ustalenia na rzeczywistym PDF hali

Ręczne sprawdzenie wykazało 72 oprawy L3 na rzucie i 1 przykład w legendzie. Dodatkowe oznaczenie osi L3 jest tekstem, nie oprawą. Zatem 74 napisy L3, 73 wizualne symbole opraw tego typu, 72 sztuki do kosztorysu. Symbol w legendzie jest około dwa razy większy i obrócony względem opraw na rzucie.

W wersji 0.5 zaznaczenie [3153,1389,16,46] wyodrębniało 1 ścieżkę / 4 segmenty oprawy i dawało 72 wyniki. Szersze [3145,1380,40,55] obejmowało 5 ścieżek / 69 segmentów, w tym inne fragmenty geometrii, i dawało tylko 12 wyników. W wersji 0.6 oba wybory oraz warianty 55×80 i 80×100 wyodrębniają ten sam kompletny korpus. Wycięcie [3154,1395,14,20] przecina oprawę: teraz pokazujemy błąd i zapisujemy wycinek, zamiast uczyć się małego znacznika wewnątrz symbolu.

Dodatkowo odtworzono dokładnie 1 trafienie dla zaznaczenia [3130,1360,80,100] na zachowanej wersji 0.5: sygnatura miała 43 ścieżki / 156 segmentów, a powiązanie L3 zostało utracone. Nie otrzymaliśmy jeszcze logu z pierwotnie zgłoszonego uruchomienia użytkownika. Nie wolno utożsamiać kontrolnego zaznaczenia z rzeczywistym gestem użytkownika ani deklarować, że znamy wersję jego uruchomionego procesu.

## Hipotezy i ich sprawdzenie

| Hipoteza | Sprawdzenie i ustalenie |
|---|---|
| Wzorzec obejmuje otoczenie | Odtworzona różnica 1/12/72 w tym samym środowisku. Poprawiono wyodrębnianie pojedynczego wydłużonego wypełnionego korpusu. Testy różnych marginesów i przecięcia symbolu. |
| Ostatni ruch myszy nie dotarł | Prostokąt był pobierany z ostatniego mouseMove. Teraz obliczany również przy mouseRelease; test bez jakiegokolwiek ruchu po naciśnięciu. |
| DPI pomnożone dwa razy | Qt przekazuje położenie logiczne; mapToScene odwraca transformację dokładnie raz. Logujemy osobno piksele fizyczne, logiczne i punkty PDF. Osobne procesy Qt 100/125/150%, różne zoomy. To emulacja skali Qt na jednym Windows, nie test trzech fizycznych monitorów. |
| GUI uruchamia inny algorytm | GUI → worker → run_detection → AIEngine → DetectionEngine. CLI, self-test i regresje korzystają z run_detection. Test integracyjny wykonuje prawdziwe zdarzenia myszy i komendę Znajdź, po czym porównuje hash wszystkich pozycji z serwisem. |
| Inne biblioteki/runtime | Usunięto fallback do ../work/.venv. Instalacja i uruchamianie sprawdzają dokładne wersje. requirements-win.lock zawiera SHA-256 kół Windows x64. Czysty venv instalowany z tych kół. |
| Błąd instalacji Windows | Odtworzony błąd PySide6 przy długiej ścieżce .venv w folderze projektu. Runtime przeniesiony do %LOCALAPPDATA%/ElectroCount/py312-06. Bez zmiany ustawienia Windows Long Paths. |
| Inny renderer / GPU | Renderer to PDFium (pypdfium2), nie PyMuPDF. Geometria jest natywna, raster OpenCV CPU, OpenCL wyłączony, seed OpenCV=0. CUDA/DirectML ani model neuronowy nie są używane w tej wersji. Profile zmieniają budżety, nie kryteria akceptacji. |
| Inny próg / zakres | Log zawiera próg projektu, strony, zakres current_page/current_document, etykietę, regułę exact_native, plan wykonania i tożsamość kodu. |
| Legenda zawyża ilość | Wyodrębniamy tabelę z nagłówkiem LEGENDA/LEGEND i ramką górną oraz bocznymi. Poszerzona skala wzorca dotyczy tylko tej tabeli. Zgodny wzorzec z tabeli trafia do legend_matches, poza ilość projektu. Brak wiarygodnej ramki nie oznacza automatycznego rozpoznania każdej legendy na dowolnym PDF. |

## Jak zebrać dowody na komputerze użytkownika

1. Uruchom Instaluj.cmd, a potem Uruchom.cmd. W tytule powinna być wersja 0.6.0.
2. Ustawienia → Tryb diagnostyczny: zapisuj wycinki.
3. Otwórz własny PDF, zaznacz cały symbol z oznaczeniem i naciśnij Znajdź.
4. Ustawienia → Otwórz logi i wycinki otwiera folder danych aplikacji.
5. Ustawienia → Uruchom test diagnostyczny albo Diagnostyka.cmd sprawdza 12 znanych symboli. Wynik PASS/FAIL i szczegóły są zapisane lokalnie.

Domyślny folder danych: %LOCALAPPDATA%/ElectroCount. Ścieżkę testową można nadpisać ELECTROCOUNT_DATA_DIR. Każda analiza w trybie diagnostycznym otrzymuje osobny katalog debug/<czas-id>/page-N; debug/latest.json wskazuje ostatni. Program sam nie wysyła żadnych logów ani rysunków.

- logs/runtime_info.json: Python, ścieżka runtime, wersje bibliotek, Qt/DPI, renderer, hash kodu i Git (jeśli dostępny), sprzęt po profilowaniu w tle.
- logs/last_detection.json: ostatnia analiza również bez obrazów, jeśli tryb wycinków jest wyłączony.
- template_log.json i selection_crop.png: oryginalne zaznaczenie, także gdy program odrzuci przecięty symbol.
- template_crop.png: dokładny wycinek wzorca po wydzieleniu geometrii; template_masked.png: wersja bez tekstu dla raster fallback. Wektorowy matcher korzysta z zapisanej sygnatury, nie z tej bitmapy.
- page_render.png: render podglądowy całej strony; jego rola i rzeczywista skala są jawne. Natywny matcher nie pracuje na renderze strony. Gdy uruchomiony jest raster, folder renders zawiera faktyczne obrazy zwracane matcherowi (kafelki/weryfikacja), z mapą bbox/scale/dpi w logu.
- candidate_NNN.png: wycinki wyników, legendy, REVIEW, innych oznaczeń oraz odrzuconych kandydatów. Bucket i indywidualne sygnały są w detection_log.json.
- detection_log.json: kompletna konfiguracja, źródło, SHA-256 PDF i kodu, wzorzec, współrzędne, liczniki, sygnały, wybrany pipeline, ostrzeżenia, czas, hash wyników.

Wycinki diagnostyczne zwiększają czas analizy. Limit obrazów kandydatów to 2000, a renderów matchera 256 MiB na analizę; pominięcia są jawnie opisane. Metadane pozostają w logu. Kandydaci odrzuceni wcześnie przez indeks geometrii mają licznik zbiorczy; nie istnieje dla nich zweryfikowany bbox ani obraz. Obrazy nie są dowodem działania OCR lub sieci neuronowej.

Replay: ustaw PYTHONPATH=src i uruchom interpreter środowiska z `-m electrocount.debug_cli --replay <detection_log.json> --pdf <lokalny-ten-sam.pdf> --output <folder>`. Porównanie bierze wszystkie położenia/etykiety/buckety, pomija czas i UUID. Dla wzorca z innego pliku podaj --template-pdf.

## Wyświetlanie wyników

Nowe zgodne trafienia są czerwone z wypełnieniem alpha 38/255, akceptowane zielone, niejednoznaczne/bez przypisania pomarańczowe, konflikty magenta, odrzucone ukryte. Obrys kosmetyczny ma 2 piksele logiczne, a marker min. 8 pikseli przy dowolnym zoomie. Zaznaczenie pogrubia obrys i powiększa marker. Wymiary geometrii i wykrywanie konfliktów nie zmieniają się. Panel osobno pokazuje znalezione elementy i legendę, bez utożsamiania liczby zatwierdzonych z liczbą znalezionych.

## Zakres weryfikacji

Test czystego środowiska oznacza nowy venv bez system-site-packages, instalację wszystkich bibliotek z kół o zweryfikowanych SHA-256 i uruchomienie tego samego GUI na tym Windows. Nie zastępuje testu na faktycznym laptopie służbowym lub GPU innych producentów. Nie ma jeszcze wydania packaged EXE; dystrybuowany jest kod i kontrolowany runtime Pythona. Nie deklarujemy zgodności nieistniejącego EXE.

## Wyniki końcowe

- Stare GUI 0.5, rzeczywisty gest 80×100 pt: 1 wynik, nazwa Symbol 01, utracona etykieta.
- Nowe GUI 0.6, identyczny gest: 73 raw / 1 legenda / 72 do zliczenia, etykieta L3.
- Nowy runtime: Python 3.12.14 x64, PySide6 6.11.2, PDFium/pypdfium2 5.13.0, OpenCV 5.0.0.93, NumPy 2.5.3, Pillow 12.3.0. PyMuPDF nie jest zainstalowany ani używany.
- GUI Qt devicePixelRatio 1.0 / 1.25 / 1.5 oraz zoom 3 / 1 / 0.2: po 72 unikalne oprawy, brak utraty oznaczeń L3, 1 legenda.
- Powtórzenie poza kontem piaskownicy, w kontekście konta Windows użytkownika: 72 oprawy, 1 legenda, zgodność GUI z serwisem oraz zapisu/odczytu.
- Hash wszystkich pozycji/etykiet/bucketów we wszystkich pięciu testach GUI: c3ab209ad7553b5a9e9304f2b4febc992d050887a2528624c7f7e68a8abd0cfd.
- Pełny zestaw: 70 PASS, 0 błędów (223,48 s). Po dodaniu kontroli zmiany kodu i komendy self-test: 9 testów diagnostycznych PASS, 1 test rzeczywistego dokumentu pominięty w tej dodatkowej próbie; rzeczywisty PDF sprawdzony niezależnie ponownie przez GUI.
- Diagnostyka instalacji: PASS 12/12; odtworzenie tego logu przez CLI: identyczny wynik.
- Zapisano debug crop, pełne logi i zrzuty GUI. Podgląd wycinka potwierdza, że geometrią wzorca jest korpus oprawy, a selection_crop obejmuje także otoczenie.

Wniosek: odtworzono i poprawiono błąd wyboru wzorca, a nie wykazano błędu mnożenia współrzędnych przez DPI. Zwiększanie progu lub dodanie modelu GPU nie rozwiązywałoby tego błędu. Różnice czasu nie oznaczają różnic ilości. Pierwotnego procesu użytkownika nie identyfikowano po samym zrzucie; tożsamość następnego uruchomienia potwierdzą logi wersji, kodu i runtime.
