# ElectroCount 0.7.5 — częściowo zasłonięte symbole

Zmiana rozszerza obecny DetectionEngine o osobną, ostrożną ścieżkę odzysku. Nie zastępuje matchera ani nie obniża jego dotychczasowych progów. Oryginalny RGB, kolorowy podgląd, dokładne oznaczenie PDF i profil elektryczny z 0.7.4 pozostają aktywne. Model Base nadal jest domyślny; nie zmieniono wag ani zależności.

## Co działa

- Tekst z warstwy PDF przecinający symbol wyznacza obszar nieznany. Oryginalny obraz nie jest modyfikowany.
- Cienka linia może zostać uznana za przesłonę dopiero po potwierdzeniu jej przebiegu po obu stronach, poza symbolem. Wewnętrzne kreski symbolu nie są automatycznie usuwane.
- Porównywane są widoczne fragmenty w obu kierunkach, w co najmniej trzech ćwiartkach. Wymagana zgodność widocznych konturów wynosi co najmniej 94%; maska może zakrywać najwyżej 28% obszaru i 28% referencyjnego tuszu. To ograniczenia algorytmu, nie deklaracja skuteczności dla dowolnego zasłonięcia.
- Pewne, zgodne oznaczenia natywne dają dodatkowe propozycje położenia pominięte przez zwykły matcher. Tekst już powiązany z poprawnym dopasowaniem wektorowym nie generuje ponownych prób.
- Każdy nowo odzyskany element otrzymuje REVIEW i pozostaje bez przypisania do grupy. Dopiero użytkownik może go przypisać. Duża punktacja widocznych fragmentów nie zmienia tej reguły.
- Niezgodne oznaczenie, np. 8 zamiast 7, pozostaje OTHER_VARIANT. Znane obszary legend są wyłączane z odzysku do zliczania.
- Diagnostyka przechowuje maskujące obiekty, zgodność widocznych konturów, udział zasłonięcia, rozkład wsparcia oraz `reconstructed_pixels=false`. Informacje zachowują się po zapisie projektu.

## Czysty przykład dla tej samej grupy

Zaznacz grupę, wybierz **Zliczanie → Wybierz czysty wzorzec tej grupy…**, zaznacz niezasłonięty przykład i kliknij **Znajdź**. Inne oznaczenie lub niezgodny profil elektryczny blokują podmianę. Identyfikator grupy zostaje zachowany. Dotychczasowe automatyczne wyniki wymagają ponownej weryfikacji; działanie można cofnąć. Esc anuluje wybieranie.

Jeżeli wybierasz przykład z nierozpoznanej legendy, nadal zaznacz **Ustawienia → Wzorzec pochodzi z legendy**, aby nie doliczyć wzorca.

## Porównanie z 0.7.4

Identyczny, deterministyczny PDF w obu uruchomieniach. Sześć przypadków, w tym cztery rzeczywiste symbole 7 (jeden z dużym ubytkiem), jeden symbol 8 i jeden inny kształt opisany 7.

| Przypadek | 0.7.4 klasyczny | 0.7.5 klasyczny / Small / Base |
|---|---|---|
| Czysty symbol 7 | MATCH | MATCH |
| 7 przecięty tekstem 20W | Pominięty | REVIEW |
| 7 przecięty linią ukośną | Pominięty | REVIEW |
| Identyczny symbol 8 z tekstem | Pominięty | OTHER_VARIANT |
| Inny kształt opisany 7 | Nie zaliczony | Nie zaliczony |
| 7 z dużym, niewyjaśnionym ubytkiem | Pominięty | Pominięty |

Licznik grupy pozostaje 1. Dwa dodatkowe poprawne elementy są dostępne do ręcznej weryfikacji. Nie jest to wzrost automatycznej liczby MATCH z 1 do 3. Większy model nie zwiększył odzysku względem Small ani trybu klasycznego na tym zestawie.

W trybie Base: czysty 7 ma ocenę łączną ok. 98,75%, zasłonięty tekstem ok. 97,77%, linią ok. 96,84%. Wszystkie mają zgodność oznaczenia 100%; zasłonięte pozostają REVIEW. Symbol 8 ma zgodność oznaczenia 0%, ocenę ok. 71,43% i decyzję OTHER_VARIANT. Te oceny nie są prawdopodobieństwem poprawności. Zestaw jest monochromatyczny, dlatego kolor jest neutralny; testy koloru pochodzą z regresji 0.7.4.

Odtworzenie:

```bash
python tools/benchmark_occlusion_075.py --output benchmark-075 --mode all
python tools/benchmark_occlusion_075.py --output benchmark-before --source-root /path/to/0.7.4 --mode classic
pytest -q
```

Podsumowanie pomiarów: [occlusion-075-results.json](occlusion-075-results.json). Czasy małej strony syntetycznej nie określają wydajności dużego projektu.

## Ograniczenia

Nie odtwarzamy ukrytej geometrii. Dowolna biała plama, gruba przesłona, za mało widocznych cech lub nieudowodnione tło nadal mogą uniemożliwić odzysk. Najlepiej zaznaczyć czysty przykład tego samego typu. Nowe propozycje oparte na oznaczeniu wymagają natywnego tekstu PDF; OCR działa jak wcześniej, ale nie daje takiego samego dowodu przesłonięcia. Nowa ścieżka obsługuje obroty bliskie wielokrotności 90°, symbole 5–150 punktów i wymaga miejsca na kontekst przy krawędzi strony. Propozycje oparte na układzie oznaczenia nie są tworzone dla wzorca oznaczonego jako LEGEND.

Testy wykonano na Linux/Qt offscreen z prawdziwym procesem aplikacji i lokalnymi modelami. Nie przeprowadzono instalacji na Windows ani ponownego testu prywatnych PDF ze służbowego laptopa, których tutaj nie ma. Poprawa na tym zestawie nie dowodzi kompletności zliczania całej dokumentacji.

## Weryfikacja wydania

Pełna regresja: **182 zaliczone, 4 pominięte**, 142,51 s. Brak prywatnych PDF jest powodem pominięć. Po tym przebiegu zmieniono wyłącznie opis wyniku zasłoniętego w UI i ponowiono przepływ GUI. Sprawdzono SHA-256 i rzeczywistą inferencję Small (384 cechy) oraz Base (768 cech). GUI uruchomiono z przeciągnięciem zaznaczenia: zgodne wyniki GUI/serwis, licznik grupy 1, dwa nieprzypisane wyniki oraz poprawny zapis/odczyt projektu.
