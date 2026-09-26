# ElectroCount 0.7.4 — raport analizy wzorca

Rozszerzono obecny DetectionEngine; generowanie i bramki weryfikacji geometrii pozostały. Punktem wyjścia jest 0.7.3 AI (commit 34ff1c84110c9bacba3bed15ebceeaf2dc005816). Większy model Base pozostaje domyślny; Small i klasyczny nadal dostępne.

## 1. RGB i reprezentacja

TemplateRepresentation przechowuje id, group_id, symbol_bbox, context_bbox, original_rgb_crop (bezstratny RGB PNG), normalized_visual_crop, color_signature, geometry_signature, visual_features, detected_label, label_bbox, label_rotation, label_position, associated_texts, source_page i source_document. Zachowano stare pola dla zgodności. Oryginał nie jest maskowany ani zamieniany na szarość; obraz dopasowania jest przygotowywany osobno. Test sprawdza równość pikseli z PDF oraz zachowanie danych po zapisie i odczycie projektu.

ColorSignature zawiera dominujący kolor pierwszego planu, histogram HSV, średnie nasycenie, udział pierwszego planu i rozkład 8×8. Porównanie rozkładu odcienia pomija achromatyczne piksele i toleruje rozmycie przez antyaliasing. Kolor zmienia ocenę, lecz sam nie odrzuca kandydata. Kopia monochromatyczna ma nieaktywny sygnał koloru (null), nie zero podobieństwa.

## 2. Oznaczenie i kontekst

W kontrolnym PDF-ie odczytano **7** z native PDF, poza ciasnym zaznaczeniem grafiki. Otoczenie obejmuje cztery strony symbolu i zależy od jego wymiarów. Zachowywane są tekst, bbox, środek, odległość, pozycja, obrót, źródło, pewność i rola wszystkich pobliskich adnotacji. OCR pozostaje fallbackiem; test zabrania jego uruchamiania przy pewnym tekście natywnym.

Role obejmują DEVICE_LABEL, CIRCUIT_REFERENCE, DEVICE_MODIFIER, DESCRIPTION i UNKNOWN. W:CR-55.1, O:RRA1.2/11.4 oraz TP04/47 są odwołaniami, nie typem urządzenia. Nie wprowadzono listy dozwolonych nazw urządzeń. Oznaczenie natywne jest porównywane dokładnie. Brak pewnego kodu kieruje kandydata do REVIEW. Obrót symbolu nie wymusza obrotu tekstu; są oceniane układy z obróconym i nieobróconym położeniem tekstu, bez preferowania szukanego kodu.

## 3. Identyczne symbole 7 i 8

Scena syntetyczna zawiera pięć identycznych kół z krzyżem: magentowe 7, magentowe 8, niebieskie 7, czarne 7 i magentowe bez numeru. Towarzyszą im niebieskie opisy obwodów wzorowane na widocznym układzie ze zrzutu. To kontrolny przykład, nie oryginalny PDF użytkownika.

W każdym trybie (klasyczny, Small, Base): **3 MATCH, 1 REVIEW, 1 OTHER_VARIANT**. Żadna 8 nie trafia do grupy 7. Oba symbole mają shape i geometry 100%; o rozdzieleniu decyduje tekst.

Wyniki Base:

| Label | Shape | Geometry | Visual AI | Color | Label score | Association | Final | Decyzja |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 7 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 95.8% | 98.8% | MATCH |
| 7 | 100.0% | 100.0% | 98.1% | 0.0% | 100.0% | 95.8% | 88.9% | MATCH |
| 7 | 100.0% | 100.0% | 88.2% | — | 100.0% | 95.8% | 96.1% | MATCH |
| brak | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 66.7% | REVIEW |
| 8 | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 95.3% | 74.9% | OTHER_VARIANT |

Oceny są heurystyczne, nie są prawdopodobieństwami. Final 74,9% przy 8 nie oznacza, że można ją zaliczyć jako 7: exact-text gate wymusza OTHER_VARIANT niezależnie od sumy. Kolor niebieskiego 7 obniża ocenę, ale nie usuwa poprawnego typu. Skala i kryteria geometrii nie zostały poluzowane.

Kontrola na tym samym PDF-ie z kodem 0.7.3: wzorzec bez rozpoznanego kodu; po podaniu żądanego 7 silnik zwracał 0 MATCH, 4 REVIEW, 1 inny wariant. W:CR-55.1 konkurowało z 7 jako DEVICE_LABEL. To potwierdza błąd powiązania tekstu na odtworzonym przypadku; nie jest dowodem naprawienia całego prywatnego rysunku.

## 4. Podgląd, liczniki i diagnostyka

Panel grup wyświetla oryginalny magentowy RGB i nazwę 7. Wykonano prawdziwy przebieg Qt: import, zaznaczenie symbolu, przygotowanie wzorca przez worker, analiza Base, zapis projektu i zrzut okna. Widoczne są 3 wyniki w grupie, 1 osobno bez przypisania oraz 8 jako inny wariant. Niepewne, nieprzypisane wykrycia nie powiększają licznika grupy.

Detection Debug pokazuje kod, kolor, źródło tekstu, bbox/obrót/pozycję oraz osobne Shape, Geometry, Visual AI, Color, Label, Association, Final i decyzję. Pokazuje też podsumowania OTHER_VARIANT. Pełne wartości pozostają w danych i logach. Definicja wzorca 9 odtwarza starsze wzorce, zachowując ich tożsamość, grupę i jawny status legendy.

## 5. Testy

- Pierwsza regresja po rozszerzeniu: 92 PASS, 1 SKIP, 7 wyłączonych testów GUI/AI.
- Po poprawieniu porównania kolorów i obrotu tekstu: 103 PASS, 1 SKIP, 7 wyłączonych.
- Nowy moduł: 14 PASS (RGB, zapis/odczyt, podgląd, 7/8 w 3 trybach, brak tekstu, kolor i monochromatyczność, cztery strony i obrót, priorytet native, legenda/migracja, liczniki i debug).
- **Końcowa pełna regresja: 176 PASS, 4 SKIP, 0 błędów, 134,88 s.** Starsze testy geometrii, tekstu, IP/EX/faz, GUI, importu, eksportu, anulowania i projektów nadal przechodzą. Cztery pominięcia wymagają prywatnych PDF-ów.
- Rzeczywiste, zweryfikowane SHA-256 modele Small i Base; Linux, Python 3.12, Qt offscreen. Nie testowano fizycznego laptopa Windows.

Odtworzenie: `Testy.cmd` lub `python -m pytest -q`; punktacja: `python tools/benchmark_template_074.py --output <folder>` po instalacji obu modeli i zależności testowych. Benchmark zapisuje syntetyczny PDF, oryginalny RGB i JSON z oddzielnymi sygnałami.

## 6. Ograniczenia

Nie ma oryginalnego PDF ze zrzutów, więc jego kompletność i dokładne ilości pozostają niezweryfikowane. Zatłoczone, współdzielone lub zasłonięte oznaczenia nadal mogą wymagać REVIEW. Tekst zamieniony na krzywe i skany zależą od OCR; błędny OCR lub niejednoznaczna rola opisu nie są w pełni rozwiązane. Role adnotacji są regułami, nie pełnym klasyfikatorem semantycznym. Geometria nadal może nie zaproponować mocno zasłoniętego symbolu. Base bywa wolniejszy na CPU. Nie trenowano nowego modelu ani nie wprowadzono automatycznej klasyfikacji wszystkich urządzeń.
