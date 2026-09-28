# Aktualny etap: 0.7.6

Gałąź feature/detection-0.7.6. Wyniki i ograniczenia: docs/detection-076.md. Powtarzalny benchmark: tools/benchmark_documents_076.py. Main nie został zmieniony. Nie przedstawiać 53/53 z jednego rzutu jako skuteczności na większości dokumentacji; CPP nadal ma duże pominięcia.

# Aktualizacja 0.7.5 — odzysk zasłoniętych symboli

Nowy moduł occlusion.py: maski natywnego tekstu i cienkich linii potwierdzonych po obu stronach symbolu; zgodność widocznych fragmentów w obu kierunkach i min. 3 ćwiartkach; dodatkowe propozycje przy nierozpoznanych oznaczeniach PDF. Każdy odzysk to REVIEW bez przypisania i bez zwiększenia ilości. Nie odtwarzać ukrytych pikseli ani nie obniżać starych progów. Komenda Zliczanie → Wybierz czysty wzorzec tej grupy… wymienia wzorzec, unieważnia stare automatyczne wyniki i wspiera cofnięcie.

Benchmark na identycznym syntetycznym PDF: 0.7.4 klasyczny — 1 MATCH, 0 REVIEW, 0 OTHER; 0.7.5 klasyczny/Small/Base — 1 MATCH, 2 REVIEW, 1 OTHER_VARIANT. Nadal nie odzyskuje dużego niewyjaśnionego ubytku. Większy model nie poprawił wyniku tego zestawu. Raport i odtwarzalny benchmark: docs/occlusion-075.md, tools/benchmark_occlusion_075.py.

Pełna regresja: 182 PASS, 4 SKIP, 142,51 s. Cztery pominięcia dotyczą prywatnych dokumentów. Po pełnej regresji dodano tylko czytelny opis częściowego zasłonięcia na liście wyników; końcowy przepływ GUI sprawdzany ponownie. GUI: prawdziwe przeciągnięcie zaznaczenia, worker Base, zgodność z serwisem, zapis/odczyt projektu. Nie deklarować sprawdzenia instalacji Windows ani całych PDF ze służbowego laptopa.

Poprzednie wersje poniżej.

# Aktualizacja 0.7.4 — pełniejsza analiza wzorca

Rozszerzenie istniejącego matchera: oryginalny RGB + osobny obraz dopasowania, wzorzec w definicji 9, kontekst i rotacja tekstu, role W:/O:/TP, odporniejszy histogram koloru, miękki sygnał koloru, osobne oceny i diagnostyka, kolorowy podgląd. REVIEW bez grupy nie zwiększa jej ilości. Aktualny raport: docs/template-074.md.

Końcowa pełna regresja 176 PASS, 4 SKIP, 0 błędów (134,88 s). Nowe 14 przypadków obejmuje 7/8, RGB, kolor, OCR/native, położenie/obrót i migrację legend. Rzeczywisty przepływ GUI Base i zapis projektu sprawdzony. Benchmark klasyczny/Small/Base: 3 MATCH (7), 1 REVIEW (brak kodu), 1 OTHER_VARIANT (8). Oryginalne prywatne PDF-y nadal nieobecne; nie deklarować potwierdzonej poprawy całego dokumentu ze zrzutów.

Poniżej historia wcześniejszych wersji.

# Aktualizacja 0.7.3 AI — DINOv2 Base i profil elektryczny

Wariant większego modelu na życzenie użytkownika: Base domyślnie, Small i klasyczny wybierane jawnie z menu. Pełne informacje: docs/ai-base-073.md. Instalator pobiera i weryfikuje Base (347 MB), diagnostyka CLI używa Base. Runtime Windows py312-07 bez zmiany bibliotek. Definicja wzorca 8; profil electrical-takeoff-v1 rozróżnia jawne IP, EX i fazy; brak lub niejednoznaczność wymaga weryfikacji.

Nie dotrenowano wag na prywatnych danych. Benchmark 3 zestawy × 3 tryby: każdy TP=2, FP=0, FN=0, review=1, other=2. Większy model nie poprawił tego już poprawnego wyniku. Base self-test 12/12 PASS i rzeczywisty przepływ GUI sprawdzony. Nadal potrzebne oryginalne PDF-y ze zdjęć i ręczne adnotacje; brak potwierdzenia jakości na laptopie służbowym.

Weryfikacja końcowa: pełny przebieg 157 PASS / 5 błędów / 4 SKIP, następnie naprawa trzech limitów GUI i dwóch powodów decyzji oraz 43 PASS / 1 SKIP / 0 błędów w dotkniętych modułach. Łączne pokrycie po poprawkach: 162 przypadki zaliczone, cztery wymagają prywatnych PDF. Nie powtarzano całości. Końcowy Base CLI 12/12 PASS i GUI sprawdzone. Szczegóły w docs/ai-base-073.md.

Poniższe sekcje są historią wcześniejszych wersji.

# Aktualizacja 0.7.2 — poprawki po testach użytkownika

Wprowadzono normalizację podzielonych prostych w ścieżkach PDF (definition_version=7), odzyskiwanie rastrowego symbolu z potwierdzoną w otoczeniu linią tła i czytelniejsze liczniki/filtr grup. Szczegóły i ograniczenia: docs/detection-072.md. Runtime Windows pozostaje py312-07; nie zmieniono przypiętych zależności ani modelu AI.

Testy w tej sesji: 149 PASS, 4 SKIP z powodu braku prywatnych PDF, 0 błędów. Linux/Python 3.12, Qt offscreen, prawdziwe OCR i DINOv2-small. To nie zastępuje próby na laptopie służbowym. Nowe testy pokazują 3/3 zamiast 1/3 lub 2/3 przy innym podziale odcinków oraz raster QP14 4/4 zamiast 3/4, A1 8/8 zamiast 6/8. Mocniejszy model pozostaje hipotezą do pomiaru na oznaczonych PDF; obecna hybryda na jednym syntetycznym przypadku nie poprawiła wyników względem klasycznego silnika.

Następny krok: otrzymać oryginalny PDF i zapisany projekt ze zdjęć z maila, odtworzyć przypadki HPØ52 i wariantów osprzętu oraz porównać logi obu komputerów. Nie deklarować, że poprawiono te konkretne przypadki na podstawie samych zrzutów.

# Historia: aktualizacja 0.7.1 — 23.09.2026

Poprawiono wyszukiwanie złożonych symboli CAD, rozróżnienie pustych/wypełnionych figur, oddzielenie przewodów i tła, zakres fallbacku rastrowego oraz wyłączenie tabel legend i potwierdzonych ramek uwag bez natywnego tekstu. Szczegóły: docs/cpp203-071.md. Definicja wzorca 6; stare wzorce są przygotowywane ponownie. Runtime i zależności pozostają 0.7, nie tworzyć nowego środowiska bez potrzeby.

Końcowe testy: 144 PASS, 0 błędów, 0 pominiętych (654,39 s), z rzeczywistą halą, pakietem PDF i CPP203. CPP203: L1=113, L1-1=76, brak wspólnych pozycji. GUI Qt przy 125%: rzeczywisty wybór myszą, 113 L1, 4 wyłączone ilustracje, identyczny hash GUI/serwis, zgodny zapis/odczyt. Nie traktować tych ilości jako kompletnego ground truth. Kilka silnie zasłoniętych symboli nadal wymaga ręcznej kontroli; EX świadomie poza automatycznym rozróżnieniem.

Następny etap: pełne ręczne adnotacje typów na trudnych PDF, pomiar FP/FN i odzyskiwanie zasłoniętych symboli bez mieszania wariantów. Narzędzie tools/benchmark_cpp203.py sprawdza 8 wzorców przez ten sam serwis co GUI. Prywatnego PDF ani wygenerowanych projektów nie publikować w repo. Dotychczasowy silnik klasyczny pozostaje domyślny, hybryda eksperymentalna.

Poniżej historia wcześniejszych wersji.

# Aktualizacja 0.7 — 22.09.2026

Priorytet: skuteczne wyszukiwanie jednego wskazanego wzorca. Brak sprzętowych profili jakości. Klasyczny silnik jest domyślny; DINOv2 + niezależne kafelki + OCR dostępne jako jawna hybryda eksperymentalna. Benchmark nie potwierdził przewagi hybrydy; nie włączać jej domyślnie samym faktem obecności AI.

Aktualna instrukcja i ograniczenia: README.md i docs/one-shot-07.md. Weryfikacja: GUI wybór z legendy L3 = 72 + 1 legenda, zapis/odczyt zgodny. Benchmark klasyczny i hybryda = 72; hybryda nadal dużo wolniejsza. Testy kodów/koloru/obwodów/monochromatyczności przechodzą. Domyślne wyszukiwanie obejmuje wszystkie dokumenty projektu.

Na tym komputerze runtime 0.7: C:/Users/tomci/Documents/Codex/ec07-venv, wskazany w ignorowanym .runtime-path. Skrót pulpitu uruchamia Uruchom.cmd i bierze ten runtime. Nie przenosić środowiska ani .runtime-path na drugi komputer. Instaluj.cmd odtwarza biblioteki z hashami i pobiera model z przypiętej rewizji. Surowe PDF-y, debug, modele i środowiska nie są w Git.

Najważniejszy następny etap: niezależne ręczne adnotacje trudnych symboli na E-01/E-07 i innych projektach, pomiar odzysku propozycji AI oraz kalibracja decyzji. Nie ma dowodu generalizacji na wszystkie oprawy. Zasada: brak pogorszenia precision/recall na dotychczasowych przypadkach.

Poniżej historia wcześniejszych wersji (nie instrukcja bieżącej instalacji).

# Aktualizacja 0.6 — 21.09.2026

Krytyczny problem został odtworzony na kodzie 0.5: zaznaczenie 80×100 pt zawierało 43 ścieżki i dawało 1 wynik. Wybór 40×55 pt dawał 12, a wąski 16×46 pt dawał 72. Poprawka w native_geometry wyodrębnia kompletny wypełniony korpus przy wszystkich tych marginesach; przecięty korpus jest odrzucany z komunikatem. Szczegóły, ograniczenia i dowody: docs/diagnostyka-06.md.

Nowe moduły: detection_service, diagnostics, document_regions, self_test_pdf, debug_cli. run_detection jest wspólnym wejściem GUI/workera/CLI/testów. GUI zapisuje source_sha256 przy starcie; worker odrzuca żądanie po zmianie kodu w uruchomionej sesji. Runtime, ustawienia, DPI i bbox są w logach lokalnych. Artefakty obrazowe opt-in z menu. Wbudowany self-test 12/12 działa także z GUI.

Potwierdzono 73 raw L3 / 1 legenda / 72 countable; automatyczne regiony legendy wymagają nagłówka i ramki tabeli. Oś konstrukcyjna L3 nie jest oprawą. Inne typy i niejednoznaczne wyniki nadal wymagają odrębnej oceny. Nie poszerzać skali kandydatów poza legendą tylko po to, żeby zwiększać ilości.

Czysta instalacja PySide6 nie udała się w długiej ścieżce repo/.venv (Windows MAX_PATH). Instalator używa teraz %LOCALAPPDATA%/ElectroCount/py312-06. requirements-win.lock ma konkretne hashe kół; check_runtime.py sprawdza instalację, Instaluj.cmd wykonuje self-test. Na komputerze diagnostycznym środowisko jest w krótkim C:/Users/tomci/Documents/Codex/ec06-venv, zapisane w ignorowanym .runtime-path. Nie przenosić .runtime-path ani venv na drugi komputer.

Testy Qt 100/125/150% na tym Windows, zoom 3/1/0.2, prawdziwe zdarzenia myszy, 72 identyczne pozycje, GUI == service i zgodny zapis/odczyt. Nowy venv z 16 pakietami z blokady; to nie test na trzech fizycznych komputerach. Nadal brak EXE/modelu neuronowego/OCR.

Poniżej historia 0.5 (nie instrukcja uruchomienia bieżącej wersji).

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
