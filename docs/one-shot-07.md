# ElectroCount 0.7 — jeden wzorzec, jednakowa jakość

## Zakres

Zmieniono wyszukiwanie wskazanego wzorca, bez automatycznej klasyfikacji wszystkich instalacji i bez treningu własnej sieci. Historyczne profile sprzętowe są przyjmowane wyłącznie jako zgodność starych ustawień; każdy daje ten sam ExecutionPlan. HardwareProfiler nie uruchamia się przy starcie ani nie wybiera jakości. Retry po OOM zmniejsza cache, zachowując etapy i model. Nie wdrożono GPU/WinML, zanim nie zostanie sprawdzona zgodność z CPU.

## Reprezentacja i decyzja

`TemplateRepresentation` zapisuje crop PNG, kontekst PNG, tekst natywny i OCR oddzielnie, sygnaturę geometrii i koloru, embedding (w hybrydzie), kandydatów tekstowych i źródłowe bbox/page. Grupy i zapis projektu pozostają zgodne; starsze wzorce są aktualizowane do definicji 5 przy analizie. Embedding jest lokalnym deskryptorem DINOv2, nie nową wytrenowaną klasą L3.

`TextRoleClassifier` używa zachowawczych reguł dla obwodów, mocy, IP/Ex i opisów rozdzielnic. Nie ma listy dozwolonych kodów urządzeń; dopuszczone są również 10, 1A i tekstowe nazwy. To heurystyka roli, nie pełne rozumienie dokumentacji. `TextEngine` zapisuje wszystkie rozważone teksty, odległość, kierunek, rolę i ocenę przestrzenną. Układ może być dowolny. Dla legend `text_layout` uczy się dominującego układu strony z pewnych powiązań, bez patrzenia na poszukiwany kod.

Dokładne oznaczenie PDF rozstrzyga EW1/EW2. Brak pewnego oznaczenia daje REVIEW; inne urządzenie daje OTHER_VARIANT. Numer obwodu nie zmienia typu. OCR działa wyłącznie jako lokalny fallback w trybie hybrydowym; dostępne oznaczenie natywne i niejednoznaczność między natywnymi kodami nie są zastępowane OCR. Wyniki OCR poniżej 0.95 pewności trafiają do REVIEW. Nie ma zamiany O→0, I→1 ani fuzzy matchingu tekstu PDF.

`color_features` porównuje histogram HSV pierwszego planu. W PDF wektorowym odczytuje również natywne kolory malowania, co oszczędza renderowanie. Monochromatyczność daje brak rozstrzygającego sygnału koloru, nie odrzucenie. `FinalDecisionEngine` zapisuje osobno visual_ai, geometry, feature, color, device_label, text_role i spatial_text. Słaby embedding sam nie wetuje silnej zgodności pozostałych cech. Oceny i próg 0.78 łącznej oceny hybrydowej są heurystyką, nie skalibrowanym prawdopodobieństwem.

## Dwie ścieżki

Klasyczna ścieżka zachowuje natywną geometrię, bitmapowe propozycje oraz niezależną weryfikację ORB/RANSAC i konturów. Hybryda dodaje DINOv2-small FP32 i `VisualRetrieval`: każdy kafelek strony trafia do enkodera, gęste deskryptory generują propozycje, lokalne dopasowanie wyrównuje je, a geometria i tekst wykonują walidację. Kandydaci obu ścieżek są scalani. DINOv2 nie jest ograniczony do wyjścia konturów. Progi, skale, modele i rozmiary kafelków są stałe na każdym PC.

Wyszukiwanie AI obejmuje całą stronę, ale nie stanowi gwarancji znalezienia wszystkich możliwych symboli, skal i orientacji. Późniejsze bramki geometrii mogą odrzucić propozycję AI; benchmark mierzy wynik po wszystkich etapach. SuperPoint/LightGlue mają interfejs, lecz aktywna implementacja lokalna pozostaje ORB/RANSAC + kontury.

## Legenda i UX

Automatyczna identyfikacja tabeli legendy nadal wymaga nagłówka i wiarygodnej ramki. Wzorzec z legendy dopuszcza różnicę skali 0.35–3.0 i uczy układu tekstu na rzucie. Dla legend nietypowych dodano Ustawienia → Wzorzec pochodzi z legendy. Źródłowe wystąpienie z legendy ma SOURCE_TEMPLATE i nie zwiększa ilości. Wystąpienie wybrane z rzeczywistego rzutu jest nadal liczone: jego wyłączenie powodowałoby błędne 71 zamiast 72. Każda decyzja o źródle jest zapisana we wzorcu.

Domyślnie przeszukiwane są wszystkie strony wszystkich dokumentów projektu. Znajdź zmienia się w Analizuję z animowanym wskaźnikiem; widoczny jest numer strony i etap. Istniejący kompaktowy panel ma animację nieokreślonego postępu podczas startu. Czerwone znaczniki mają kosmetyczny obrys 2px, alpha 38/255 i minimalny wymiar ekranowy 8px; aktywny wynik 3.2px i alpha 50. REVIEW jest pomarańczowy, konflikt magenta, zatwierdzony zielony.

## Benchmark i dowody

Benchmark porównuje identyczne pliki, bbox i adnotacje, stosując dopasowanie lokalizacji 1:1 (IoU ≥ 0.3). Dziewięć scen D1, AW2, EW1, QP14, AS1, 1A, 2A, 10, 7N zawiera trzy prawidłowe urządzenia, w tym kopię monochromatyczną i różne obwody, oraz podobny element EW2. Sceny są syntetyczne i mają wspólny kształt; potwierdzają reguły tekstu/koloru, nie jakość na całej różnorodności symboli.

Na każdej z dziewięciu scen oba silniki uzyskały TP=3, FP=0, FN=0, precision/recall/F1=1. Na rzeczywistej hali, przy wzorcu L3 wybranym w legendzie: oba silniki TP=72, FP=0, FN=0, precision/recall/F1=1, dodatkowo 1 wyłączony symbol legendy i 63 nieprzypisane propozycje REVIEW. Dla hali lokalizacje referencyjne są bbox oznaczeń 72 wcześniej ręcznie sprawdzonych opraw, nie bbox wytworzone przez matcher. To nie benchmark segmentacji korpusu.

Hybryda zakodowała 407 kafelków i wygenerowała 1331 dodatkowych propozycji; żadna nie dodała nowego poprawnego urządzenia w tym przykładzie. W porównaniu po poprawie obrotu wzorca klasyczny silnik potrzebował ok. 12.7 s, hybryda ok. 592.5 s. W tle działały również testy, więc nie jest to izolowany benchmark wydajności. Początkowa hybryda znalazła 55/72; poprawiono wyrównanie rotacji i współdzielenie renderera. Ostateczna zmiana reguły łącznej oceny została dodatkowo sprawdzona na wszystkich 553 zapisanych zestawach sygnałów — bez zmiany koszyków i ilości. To jawnie replay decyzji, nie ponowne wykonanie enkodera.

**Hybryda nie wykazała przewagi precision i recall, więc nie jest domyślna.** Nie należy sprzedawać samego dodania modelu jako poprawy skuteczności. Następny etap: ręcznie opisane trudne przypadki z innych rzeczywistych projektów, poprawa wyrównania i geometrii propozycji odzyskiwanych przez AI oraz pomiar pełnego recall wraz z czasem.

Test GUI wykonywał rzeczywiste zdarzenia Qt przy skali 125%, zaznaczenie [5080,420,57,20] w legendzie, Find, zapis i ponowne otwarcie. Wynik: 72 unikalne pozycje, 1 legenda, zgodny hash GUI/serwis i zgodny zapis/odczyt; brak błędów. To jeden Windows i emulacja skali Qt, nie test na drugim fizycznym komputerze. Podstawowa pełna seria: 131 testów zaliczonych; końcowe dodatkowe testy opisuje docs/testy.md.

## Moduły i instalacja

Nowe: `template_representation`, `color_features`, `text_roles`, `text_layout`, `final_decision`, `ocr_engine`, `render_session`, `benchmark`, `ai/visual_encoder`, `ai/retrieval`. ModelManager ładuje lokalny encoder z SHA-256. Zestaw 30 bibliotek ma dokładne wersje i hashe Windows x64/Python 3.12. PP-OCRv4 jest zawarty w przypiętym wheel RapidOCR 1.4.4. DINOv2 pobierany jest tylko podczas instalacji; podczas analizy nie ma połączeń sieciowych. `Instaluj_AI.cmd` służy również do naprawy brakującej wagi.

Model: [DINOv2-small, opis Meta/Hugging Face](https://huggingface.co/facebook/dinov2-small), [konwersja ONNX](https://huggingface.co/onnx-community/dinov2-small), rewizja `8b1f705a3a7f6f062f6bdd21986c1583d3ef105d`, SHA-256 `f22797eabf810a75e41de68d378541ebea372122b25c4ce3ef25ff618250c20a`; licencja modelu Apache-2.0. [RapidOCR](https://github.com/RapidAI/RapidOCR), Apache-2.0. Preprocessing DINOv2 jest jawnie dostosowany do symboli: biały kwadrat zachowujący proporcje, 224px bez obcinania, normalizacja ImageNet. Trening, kontekstowy VLM, graf instalacji, WinML/GPU i natywny parser DWG pozostają nieaktywne.
