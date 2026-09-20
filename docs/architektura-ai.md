> Wersja 0.5: warstwę wykonawczą fasady AI rozszerzono o lokalną geometrię i obracany układ oznaczenia. Szczegóły: [detekcja-05.md](detekcja-05.md). Interfejsy modeli, kontekstu i treningu opisane poniżej zachowano.

# Architektura AI — audyt i etap 1

## Stan wyjściowy

GUI i parsery są już oddzielone. FileImportManager kieruje PDF do PDFium, a DWG/DXF do nieaktywnego CADEngine. Detekcja V2 rozdziela generowanie kandydatów, weryfikację cech/geometrii oraz dopasowanie tekstu. ResultsManager uzgadnia nowe wyniki z istniejącymi decyzjami. ConflictEngine kontroluje nakładanie między grupami. Praca analityczna odbywa się w QProcess i dopiero kompletny wynik jest nakładany na projekt. SQLite przechowuje transakcyjny snapshot i odwołania do lokalnych kopii źródeł.

Brakowało nadrzędnego kontraktu przyszłych sygnałów AI, kontroli zasobów zależnej od sprzętu oraz wyraźnego rozróżnienia „wykryta karta” / „dostępny runtime” / „przetestowana inference”. Nie było lokalnego katalogu wersji modeli ani kontraktu danych treningowych. Te luki obejmuje etap 1.

## Aktualny przepływ

GUI → JobManager → worker → AIEngine → DetectionEngine V2 → wyniki → ResultsManager → ConflictEngine → decyzje użytkownika.

Równolegle, niezależnie od projektu: PerformanceController → HardwareProfiler w osobnym procesie → pomiary → ExecutionPlan. Plan jest dołączany do żądań workerów. Nie modyfikuje progu dopasowania, normalizacji tekstu ani zasad przypisania do grup.

AIEngine zachowuje dotychczasowe wywołanie find i format wyników; dokłada informacje o aktywnych etapach i nullable SignalBreakdown. Dane grup, statusy i liczności nadal obsługuje istniejąca warstwa domenowa. W projekcie zapisywane są signals i pochodzenie pipeline; profil sprzętowy jest lokalnym ustawieniem użytkownika.

## Granice modułów

| Moduł | Aktywny zakres | Przygotowane rozszerzenie |
|---|---|---|
| Document parser | PDFium: tekst, render, ograniczona ekstrakcja ścieżek | Typ vector/raster/hybrid, CAD entities/blocks |
| Candidate/Geometry | Sygnatury wektorowe, raster multi-scale, OpenCV/RANSAC | IFeatureMatcher, lokalny adapter LightGlue |
| TextEngine | Dokładny tekst natywny z położeniem | OCR tylko gdy natywny tekst niedostępny |
| ModelManager | Manifesty, role, wersje, checksum, wymagania, kontrola ścieżki | Ładowanie zweryfikowanych modeli, aktualizacja/import |
| AIEngine | Fasada deterministycznego pipeline i zapis sygnałów | IVisualSymbolEncoder i fusion po walidacji jakości |
| ContextEngine | Zwraca brak dowodów, ambiguous=true | Graf relacji DocumentEntity, legenda |
| IVisionReasoner | Kontrakt odpowiedzi dla istniejącego kandydata | Lokalny VLM tylko do niejednoznaczności |
| TrainingDatasetManager | Nieaktywny interfejs record i schemat przykładu | Osobny lokalny dataset i zdarzenia użytkownika |

Brak modelu = brak oceny (`null`). Żaden moduł nie zwraca udawanego embeddingu ani wyniku kontekstowego. ReasoningResult nie ma pola ilości ani mechanizmu tworzenia nowych detekcji. Future Final Decision Engine wymaga odrębnej implementacji i walidacji; nie zastępujemy teraz sprawdzonych reguł decyzji.

## ModelManager

Katalog: models/<model>/<version>/manifest.json, obok artefakt wag. Pola: name, version, role, filename, checksum SHA-256, required_ram_mb, required_vram_mb, backends (CPU/WinML/CUDA). Role: symbol_encoder, feature_matcher, ocr, context. Model może mieć wiele wersji bez reinstalacji aplikacji.

list_models pokazuje istnienie/stan manifestu, nie udaje sprawdzenia wag. inspect wykonuje hash i kontroluje ścieżkę. Nawet poprawny checksum ma active=false: w etapie 1 nie istnieje loader modeli ani automatyczny wybór adaptera inference. Manifesty są danymi, nie wykonywanym kodem. Nie ma pobierania z sieci.

## Profilowanie i ograniczenia zasobów

Odczyty Windows korzystają z GlobalMemoryStatusEx, topologii procesora i DXGI. Karty programowe są pomijane. Pamięć dedykowana i współdzielona są oddzielnymi wartościami. DirectX 12 jest sprawdzany przez D3D12CreateDevice bez tworzenia urządzenia. Runtime Windows.AI.MachineLearning i sterownik CUDA są odnotowane oddzielnie od dostępnych adapterów aplikacji. Zainstalowane ONNX Runtime może zgłosić providery, ale sama lista nie potwierdza, że model działa na GPU.

Benchmark używa anonimowego syntetycznego PDF i obrazu z geometrią, nie dokumentów użytkownika. Wykonuje do trzech pomiarów PDF i ORB, z terminem 8 s wewnątrz procesu. GUI ma niezależny watchdog 15 s obejmujący uruchomienie, importy bibliotek i sondy. Porażka/timeout daje Eco. Pomiar RAM dotyczy rzeczywistego working set / peak procesu. Inference embedding/GPU i użycie VRAM są jawnie pominięte, dopóki nie ma modeli i adapterów. Nie zastępujemy tych pomiarów mnożeniem macierzy CPU.

AUTO Standard wymaga >=2500 MB wolnego RAM, >=2 rdzeni oraz zmierzonego renderu <=150 ms i ORB <=200 ms. W przeciwnym razie Eco. To początkowe progi polityki, nie uniwersalna klasyfikacja sprzętu. AUTO nie wybiera Enhanced/Maximum bez przyszłych pomiarów inference; wymuszenie profilu ustala wyłącznie zasoby aktualnych etapów.

| Profil | Maks. wątków OpenCV | Cache RAM |
|---|---:|---:|
| Eco | 1 | 24 MB |
| Standard | 4 | 48 MB |
| Enhanced | 6 | 72 MB |
| Maximum | 8 | 96 MB |

Wątki są ograniczane liczbą CPU z pozostawieniem jednego wątku logicznego, o ile to możliwe. Przy wolnym RAM <1500 MB cache nie przekracza 24 MB. Cache dyskowy PDF pozostaje ograniczony do około 256 MB. Stały limit 40 000 segmentów dotyczy wszystkich profili i powoduje jawne przejście do istniejącej analizy kafelkowej; nie pozostawia niepełnego indeksu wektorowego.

MemoryError, OpenCV StsNoMem i jawny BackendResourceError skutkują obniżeniem profilu, zwolnieniem referencji i ponowieniem całej operacji. Liczba prób jest ograniczona poziomami profilu. Błędy dokumentu nie są uznawane za błędy zasobów. Przyszły adapter ma tłumaczyć OOM, błąd providera i limit czasu inference na BackendResourceError. Natywna awaria procesu jest dziś izolowana i zgłaszana; automatyczny restart modelu po takim crashu nie jest jeszcze zaimplementowany. Przyszły watchdog inference musi być osobny od zegara całej analizy dokumentu.

## Dataset — kontrakt, nie zbieranie danych

TrainingExample zawiera wersję schematu/datasetu, identyfikator projektu, hash dokumentu, stronę, bbox, grupę, kod odczytany/poprawiony, akcję, obrót, format, czas i split. DatasetAction obejmuje accept/reject/manual_add/change_group. DatasetSplit rozróżnia TRAIN/VALIDATION/TEST/BENCHMARK. record obecnie zwraca False i niczego nie zapisuje. Nie podłączono zdarzeń GUI do kolekcji. Benchmark nie jest używany do treningu, którego ten etap w ogóle nie uruchamia.

W przyszłym etapie trzeba dopiero dodać writer wersjonowanych katalogów, cropy, kontrolę jakości adnotacji, deduplikację dokumentów, rozdział projektów między splitami i eksport. Dostarczony „AI trenig pack” wykorzystano jedynie do lokalnych testów zgodności i pamięci.

## Następny etap

1. Typ dokumentu i spójne reprezentacje tekstu/geometrii. W E-01/E-07 napisy są ścieżkami; dodać wymienny OCR fallback, bez utraty zasady native text first.
2. Context graph oraz model legendy z ręcznym zaznaczaniem. Ambiguous pozostaje REVIEW.
3. Oznaczyć referencyjne elementy w reprezentatywnych PDF i zamrozić osobny benchmark. Bez ground truth nie ogłaszać precision/recall/F1.
4. Dopiero potem porównać lokalny encoder proof of concept z obecną bazą, zmierzyć inference na CPU/GPU i uzasadnić dalsze wdrożenie. Trening i VLM to dalsze osobne etapy.

## Źródła techniczne sprawdzone podczas wdrożenia

Wartości pamięci adaptera odpowiadają polom [DXGI_ADAPTER_DESC1](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/ns-dxgi-dxgi_adapter_desc1). Backend jest rozdzielony od algorytmu zgodnie z ideą [ONNX Runtime Execution Providers](https://onnxruntime.ai/docs/execution-providers/). [DirectML](https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html) nie jest utożsamiany z aktywnym adapterem WinML aplikacji.
