# ElectroCount 0.7.3 AI

## Większy model

Na życzenie użytkownika ta wersja domyślnie uruchamia DINOv2 Base ONNX FP32 na CPU. Instalator pobiera 346 627 111 bajtów (około 347 MB), weryfikuje SHA-256 i wykonuje prawdziwą inferencję. Model zwraca 768 cech zamiast 384 w Small. Instalacja wymaga internetu; analiza rysunków odbywa się lokalnie. Brak lub uszkodzenie modelu daje jawny błąd, bez samoczynnej zmiany modelu.

Ustawienia → Model analizy pozwalają wybrać Base, Small albo tryb klasyczny. Small można doinstalować poleceniem `Instaluj_AI.cmd --model small`. Biblioteki i runtime Windows py312-07 pozostają bez zmian. ZIP zawiera kod; model pobiera instalator.

Źródło modelu: https://huggingface.co/onnx-community/dinov2-base oraz https://github.com/facebookresearch/dinov2/blob/main/MODEL_CARD.md.

- Rewizja Base: `31ef06cac16d5d301c5930d147002a058c85a5e4`.
- SHA-256 Base: `320d1012a6fc65b101fc85ca30ee7a47b2e4f6a2e8bd78fb9d7036def0e30cb0`.
- Pełny obraz symbolu jest zachowany przez dopełnienie do kwadratu; nie stosujemy centralnego wycięcia.
- Model jest ponownie używany pomiędzy stronami, a embeddingi różnych modeli nie są porównywane.

## Dostosowanie do przedmiaru elektrycznego

Profil `electrical-takeoff-v1` rozdziela kod urządzenia od jawnych cech IP, EX i 1~/3~. Zaznaczenie wzorca powinno obejmować symbol, kod typu i odpowiednie cechy. Wzorce starsze niż wersja definicji 8 są przygotowywane ponownie.

- IP20 i IP44 oraz 1~ i 3~ nie są automatycznie łączone w ten sam wariant.
- Brak wymaganej cechy daje wynik do weryfikacji. Program nie uznaje braku IP za IP20.
- Cecha współdzielona między bliskimi symbolami, sprzeczne oznaczenia lub słaby odczyt OCR wymagają weryfikacji.
- Numery obwodów, np. TP04/47 i TP04/49, nie rozdzielają identycznego urządzenia na typy.
- Wysokie podobieństwo AI nie znosi kontroli geometrii, tekstu i cech elektrycznych.

To dostosowanie reguł analizy i interfejsu. Wagi DINOv2 są ogólnego przeznaczenia i nie zostały dotrenowane na prywatnych rysunkach użytkownika.

## Weryfikacja i ograniczenia

`tests/test_electrical_ai.py` sprawdza trzy zestawy (IP44, EX, 3~) w trybach klasycznym, Small i Base. Każdy zawiera dwa poprawne symbole o różnych numerach obwodów, inny wariant, brak oznaczenia, inny kod urządzenia i błędną geometrię. Weryfikujemy lokalizacje przez IoU ≥ 0,7, nie samą liczbę wyników. Są też testy niejednoznaczności, rzeczywistej inferencji Base, braku pobierania podczas inferencji i jawnego błędu modelu.

Porównanie można odtworzyć: `python tools/benchmark_electrical.py --output <folder>`. Wszystkie tryby dostają identyczne PDF-y i niezależne kopie tego samego wzorca. Późniejsze przypadki mogą korzystać z cache modelu i obrazów; podanych czasów nie należy traktować jako porównania wydajności komputerów.

Brakuje oryginalnych prywatnych PDF-ów ze zdjęć użytkownika. Testy wymagające tych dokumentów są jawnie pomijane. Testy Linux/Qt offscreen nie zastępują uruchomienia na fizycznym laptopie Windows. Nie potwierdzono poprawy skuteczności Base na rzeczywistych rysunkach ani przewagi na prostych przykładach syntetycznych. Do takiego wniosku potrzebne są oryginalne PDF-y i ręcznie zweryfikowane pozycje urządzeń.

### Wyniki porównania 25.09.2026

| Tryb | Zestawy IP44 / EX / 3~ | Trafienia na zestaw | FP / FN | Brak cechy do weryfikacji | Inne warianty |
|---|---|---:|---|---:|---:|
| Klasyczny | 3/3 poprawne | 2/2 | 0 / 0 | 1 | 2 |
| DINOv2 Small | 3/3 poprawne | 2/2 | 0 / 0 | 1 | 2 |
| DINOv2 Base | 3/3 poprawne | 2/2 | 0 / 0 | 1 | 2 |

Model Base przeszedł także self-test 12/12 i rzeczywiste wywołanie z GUI: dwa G1 IP44, jeden G1 bez IP do ręcznej weryfikacji, osobno G1 IP20 i G2. W logu potwierdzono `hybrid_base` i przypiętą rewizję modelu.
