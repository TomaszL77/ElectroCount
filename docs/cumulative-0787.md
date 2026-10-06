# 0.7.8.7 — oznaczenia opraw i wcześniejsza wiedza

Oznaczenia urządzeń bywają w PDF-ie narysowane jako wypełnione kontury zamiast tekstu. Lokalny OCR może odczytać pełny kod także wewnątrz zaznaczenia; pojedynczy znak lub nagłówek legendy nie zastępuje oznaczenia. Dla niewielkich kolorowych konturów zastosowano odczyt bezpośrednio z ich rodzimych granic, w wysokiej rozdzielczości. Ten odczyt przegląda wszystkie typy niezależnie od aktualnie szukanego kodu. Obsługa pozostałych dokumentów nadal korzysta z tekstu PDF i lokalnego OCR.

Gdy czytelny kod leży obok symbolu, analiza porównuje osobno grafikę i kod. Sygnatura analityczna usuwa tylko ścieżki rozpoznanego zewnętrznego napisu. Oryginał RGB, pełna sygnatura, wszystkie zaznaczone części i prostokąt pozostają zapisane. Wnętrze symbolu i różnice w wypełnieniu nadal podlegają kontroli. Dla propozycji opartych na odczytanym konturze kodu pełny zgodny kontur kolorowego symbolu może potwierdzić grafikę mimo nieudanej weryfikacji ORB; tło architektoniczne nie jest wtedy traktowane jako część kolorowego urządzenia. Sam kod nie wystarcza do dodania ilości.

Białe wypełnienie obejmujące całe zaznaczenie spoza jego granic traktowane jest jako papier. Wewnętrzne białe detale nie są usuwane. Tabela legendy może składać się z osobnych zamkniętych komórek. Rozpoznana legenda jest wyłączana ze zliczania urządzeń. Ręcznie nadana nazwa grupy jest zachowana; błędnie odczytany nagłówek jest naprawiany przy ponownej analizie. Aktualizacja starego wzorca nie zastępuje zatwierdzonych części `reviewed_apparatus_parts`.

## Uczenie

Trening zawsze używa wspólnej bazy ocen. Poprawne ręcznie dodane pominięcia oznaczaj **Poprawny**. **Błędny kształt** oznacza urządzenie niepasujące graficznie do wzorca. Inne oznaczenie przy podobnej grafice to **Inny wariant / oznaczenie**. Nie trzeba odrzucać poprawnych przykładów, żeby odblokować trening.

1. **Uczenie → Uczenie AI → Import danych**: wczytaj wspólną bazę ocen z osobnego pakietu.
2. **Import modelu**: wczytaj dostarczony plik `.ecmodel`, następnie **Użyj tego modelu**.
3. Zbieraj kolejne oceny. **Wytrenuj wstępnie** lub **Wytrenuj model** ponownie uczy na wcześniejszych i nowych przykładach. Wstępny trening wymaga 20 poprawnych i 20 rzeczywiście niepasujących kształtów; pełny wymaga osobnych dokumentów walidacyjnych i testowych.
4. **Eksport danych** i **Eksport modelu** pozwalają przenieść wiedzę na inny komputer. Sam model wystarcza do korzystania, baza ocen jest potrzebna do kolejnego wspólnego treningu.

Import zachowuje nowsze lokalne oceny oraz poprawki użytkownika przed ocenami przygotowanymi przez asystenta. Przy nauce wstępnej lokalizacje kontrolne są utrwalane w metadanych przykładów; dodanie kolejnego PDF-u nie zmienia wcześniejszego podziału. Starsze importowane pakiety mogą zachować swój poprzedni podział. Skrót bazy modelu uwzględnia również obrazy i ten podział.

Otwarcie PDF-u ani znalezienie kandydata nie nadaje mu automatycznie prawidłowej oceny. Dokument legendy daje przykłady wzorców, a nie potwierdzenie liczby urządzeń na rzucie. Wyniki treningu mierzą ocenione pary obrazów; skuteczność na nowym projekcie i kompletność całego arkusza wymagają osobnej kontroli.

## Kontrola zmiany

Ograniczony zestaw obejmuje zachowanie pełnego oryginału, biały papier, oddzielenie kodów, inny typ, zamknięte komórki legendy, nazwy grup w interfejsie, import ocen, zamrożenie lokalizacji kontrolnych i trening. Dodatkowo sprawdzono konkretne wzorce na przekazanych prywatnych PDF-ach oraz zachowanie wcześniejszych odłożonych par. Nie wykonywano instalacji Windows ani pełnej historycznej regresji. Starsze testy korzystające z usuniętych plików wejściowych lub wcześniejszej definicji wzorca pozostają poza domyślnym zestawem.
