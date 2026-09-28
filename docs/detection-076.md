# ElectroCount 0.7.6 - wyniki i przegląd detektora

Wersja testowa. Potwierdzona poprawa na rzucie piętra +1; dokumenty CPP nadal nie spełniają celu skuteczności. Nie deklarujemy pracy na większości dokumentacji.

## Wyniki na rzeczywistych PDF

Tryb Classic, próg 0,82, CPU. Identyczne zaznaczenia dla obu wersji. Przeszukiwana jest cała strona; dla CPP ocena poprawności dotyczy wyłącznie ręcznie sprawdzonych obszarów, nie całego rysunku.

| Dokument / typ | Poprawne 0.7.5 | Poprawne 0.7.6 | Referencja | Pominięcia 0.7.6 |
|---|---:|---:|---:|---:|
| Piętro +1 / 7 | 8 | 10 | 10 | 0 |
| Piętro +1 / 8 | 7 | 12 | 12 | 0 |
| Piętro +1 / 9 | 3 | 5 | 5 | 0 |
| Piętro +1 / 10 | 15 | 26 | 26 | 0 |
| CPP204 / AW3 | 1 | 3 | 8 | 5 |
| CPP204 / EW3 | 1 | 1 | 2 | 1 |
| CPP203 / AW4 | 1 | 1 | 6 | 5 |

Piętro +1: 33/53 -> 53/53 prawidłowych opraw. Wszystkie 53 trafienia dodatkowo obejrzano na wycinkach z oryginalnego PDF. Brak pomyłek między 7, 8, 9 i 10 w tych wynikach. Wersja 0.7.6 nadal dolicza po jednym symbolu legendy dla każdego z czterech typów (razem 4). Aplikacja pokazuje zatem 11, 13, 6 i 27; to nie są czyste ilości urządzeń na rzucie. W 0.7.5 doliczano 3 wpisy legendy. Po zastosowaniu wyników do czterech grup ConflictEngine zwrócił 0 konfliktów.

CPP204: obszar [680,595,480,220] punktów PDF; 8 AW3 i 2 EW3. CPP203: [50,270,600,310]; 6 AW4. We wskazanych obszarach brak fałszywych automatycznych trafień i brak odzysków do REVIEW. Nie zweryfikowano wszystkich trafień poza tymi obszarami. Na całej stronie otrzymano odpowiednio 5 AW3, 8 EW3 i 2 AW4; te liczby nie są potwierdzonym przedmiarem. Dla AW4 użyto czystego wzorca z rzutu, więc nie porównujemy tego testu z wcześniejszą próbą wzorca z legendy.

Oznaczenia wzorców 7, 8, 9 i 10 odczytano z PDF; AW3, EW3 i AW4 przez OCR. W bazowej wersji Classic etykiety trzech wzorców CPP były puste. Oryginalne RGB jest zachowane.

## Kontrola większego modelu

Dla oprawy 7 model Base uzyskał 10/10 prawidłowych trafień i 1 wpis legendy, tak samo jak Classic. Nie poprawił skuteczności tego przypadku. Zarejestrowano około 189 s dla Base i 39 s dla Classic, ale procesy testowe działały współbieżnie, więc nie jest to kontrolowany benchmark wydajności. Nie wykonano pełnego porównania Base dla pozostałych typów.

## Co zmieniono

1. Liczenie przecięć pomija niestabilne kontakty przy końcach odcinków, ale nadal sprawdza właściwe przecięcia wewnętrzne. Kontrola liczby i rodzaju kresek, brakujących cech oraz wypełnienia pozostaje. W starym detektorze oprawa o geometry score=1.0 mogła zostać odrzucona przez 1/3/5 pozornych przecięć.
2. Dodano hipotezy obrotu z pełnych granic obiektu oraz przesunięcie bez skalowania, gdy różnica wymiarów mieści się w kwantyzacji. Pełna geometria musi zatwierdzić każdą hipotezę. Błąd współrzędnych 0,12 punktu jest uwzględniany w obu osiach, nie tylko jednej.
3. Nakładający się kontur okręgu jest normalizowany wyłącznie wtedy, gdy pokrywa już istniejącą, wypełnioną granicę w tym samym kolorze. Oddzielne wewnętrzne cechy nie są usuwane.
4. Weryfikacja małych symboli korzysta z lokalnego renderu o zwiększonej rozdzielczości. Usunięto blokadę poszukiwania przy natywnych oznaczeniach dla symboli poniżej 5 punktów. Sam tekst nie jest dowodem obecności urządzenia. Wąskie lub duże symbole nie uzyskują automatycznego zatwierdzenia z takiego wycinka; częściowo zasłonięte nadal wymagają REVIEW.
5. OCR działa niezależnie od modelu DINOv2. Usuwanie powtórzonych hipotez geometrycznych odbywa się przed OCR, co ogranicza zbędne odczyty. Tekst natywny ma pierwszeństwo. OCR odczytany z samej grafiki nie jest automatycznie uznawany za kod urządzenia.
6. Definicja wzorca 10 odtwarza starsze sygnatury po otwarciu i ponownym wyszukiwaniu.

## Ocena kolejności i konfliktów

Zachowano: dokładne rozróżnianie etykiet, kontrolę IP/EX/faz, odrzucanie brakujących kresek/wypełnienia innego typu, REVIEW bez pewnego kodu i kontrolę konfliktów między grupami. Kolor pozostaje dodatkowym sygnałem, a nie jedyną przyczyną odrzucenia.

Poprawiono: niestabilny test topologii; zbyt małą rozdzielczość; zależność OCR od ciężkiego modelu; powtarzanie OCR dla nakładających się hipotez. Nie usunięto masowo zabezpieczeń.

Pozostałe ograniczenie: generator natywny nadal może odrzucić symbol przed niezależną weryfikacją obrazu. Ścieżka propozycji po oznaczeniach korzysta z tekstu natywnego, więc nie ratuje w pełni dokumentów CPP, gdzie tekst jest grafiką. To ważniejszy kolejny problem niż legenda lub mocniejszy model.

Nie wdrożono jeszcze biblioteki wielu wzorców jednej grupy ani globalnej klasyfikacji wszystkich typów. Ta iteracja zachowuje obecną architekturę i daje zmierzone wyniki do zaplanowania następnej.

## Następne kroki

1. Dla CPP zachować odrzucone hipotezy o zgodnym obrysie i sprawdzać je niezależnym porównaniem konturów w wysokiej rozdzielczości, a dopiero potem rozstrzygać typ przez OCR kontekstu. Nie zastępować tego globalnym obniżeniem progu.
2. Rozdzielić tekst wewnętrzny M1/M5 od zewnętrznego typu AW3/AW4; sprawdzić także wybór wzorca z legendy i obrócone symbole EW3.
3. Zmierzyć poprawę na tych samych obszarach oraz na nowych, nieużytych do doboru parametrów. Dopiero później oceniać korzyści z wielu potwierdzonych wzorców lub wyspecjalizowanego modelu.

## Odtworzenie pomiarów

`python tools/benchmark_documents_076.py --pdf /sciezka/rysunek.pdf --suite floor --output /sciezka/wyniki`

Dostępne zestawy: floor, cpp204, cpp203; tryby: classic, hybrid, hybrid_base. Opcjonalne --label ogranicza pomiar. JSON w docs/benchmarks-076 zawiera SHA-256 dokumentów, zaznaczenia, zakres audytu, liczbę braków i fałszywych trafień. PDF-y użytkownika nie są częścią repozytorium.

## Regresja

Końcowa pełna regresja: **201 PASS, 4 SKIP, 0 FAIL**, 158,48 s. Pominięte testy wymagają dodatkowych prywatnych PDF. Wykonano rzeczywiste testy modeli Small/Base oraz GUI; nie sprawdzono instalacji na Windows. 19 nowych przypadków obejmuje wszystkie 16 kombinacji 7/8/9/10, stabilne przecięcia, małe propozycje i odrzucanie brakującej kreski. Modele Small i Base zweryfikowano przez SHA-256 oraz prawdziwą inferencję. Wcześniejsza próba wykazała uszkodzoną lokalną kopię Small; model pobrano ponownie, bez zmiany algorytmu ani oczekiwań testów.
