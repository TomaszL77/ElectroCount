# ElectroCount 0.7.8 — własny mały model i oceny użytkownika

Podstawa: 0.7.7.2, commit d3fee3f3635d310820215b3ef1897e4aac671912. Renderowanie kafelkowe i dokładny podgląd zaznaczenia pozostają zachowane.

## Co jest gotowe

- Menu **Uczenie → Uczenie AI**: dokumenty, oceny, podział całych PDF-ów, wycinki, trening, historia modeli, porównanie i eksport.
- Akceptacja trafienia zapisuje pozytywny przykład, odrzucenie — błędny kształt. Ręczne dodanie pominięcia zapisuje pozytywny przykład. Zmiana grupy zapisuje wariant dla poprzedniej grupy i potwierdzony przykład dla wybranej.
- Menu pozwala oznaczyć wybrany element jako inny wariant lub niepewny. Te rekordy pozostają w bazie, ale nie uczą wizualnego podobieństwa. Znany konflikt oznaczeń jest traktowany jako wariant, a nie jako błędny kształt.
- Automatyczne wyniki bez oceny użytkownika nie są danymi treningowymi. Checkbox **Zapisuj moje oceny** wyłącza zbieranie.
- Oceny są zapisywane w osobnym trwałym procesie. Cofanie i ponawianie zmiany aktualizuje tylko dotknięte oceny; nie utrwala jednego wykrycia jako poprawnego w obu grupach.
- Przycisk **Wytrenuj model** uruchamia prawdziwe uczenie wag małej sieci na lokalnym CPU. Przycisk **Przerwij trening** zachowuje już zapisane dane i poprzednie modele.
- **Użyj tego modelu** wybiera wersję do następnego wyszukiwania. Trening nie zastępuje sam aktywnego modelu. Starsze wersje można wybrać ponownie.
- Eksport/import danych ZIP, modelu `.ecmodel` oraz raportu JSON. Plik modelu działa na innym komputerze i bez internetu; nie zawiera ścieżki wymaganej do oryginalnego PDF-u.

## Jak zacząć

1. Otwórz swój PDF w 0.7.8, zaznacz wzorzec i kliknij Znajdź.
2. Akceptuj poprawne trafienia, odrzucaj błędne i zaznaczaj pominięcia przez Dodaj ręcznie.
3. Otwórz panel Uczenie AI. Oceny i wycinki są już w bazie.
4. Zbierz przykłady z co najmniej czterech różnych PDF-ów. Początkowo dwa pierwsze służą do uczenia, trzeci do walidacji, czwarty do testu. Można zmienić podział całego PDF-u w panelu.
5. Minimum na przycisk treningu: uczenie 20 poprawnych + 20 błędnych z co najmniej dwóch PDF-ów; walidacja 5 + 5; test 5 + 5. To minimum techniczne do pierwszej próby, nie gwarancja dobrej generalizacji. Setki zróżnicowanych przykładów będą bardziej wartościowe.
6. Kliknij Wytrenuj model, obejrzyj porównanie i wybierz Użyj tego modelu.

Cały PDF ma jeden podział, ustalany według skrótu jego zawartości. Kopia tego samego PDF-u ani druga jego strona nie może równocześnie trafić do uczenia i testu. Walidacja wybiera próg; dokumenty testowe nie są wykorzystywane do gradientów, augmentacji ani doboru progu. Powtarzane oglądanie testów przez operatora nadal może prowadzić do dostrajania procesu pod znany zestaw — do niezależnego audytu potrzebne będą dodatkowe dokumenty.

## Mała sieć i wyszukiwanie

To pierwsza sieć porównująca dwa wycinki, nie zbiór globalnych klas „7” lub „AW4”. Wejście zachowuje proporcje i zawiera obraz, kontury oraz informacje o kolorze. Wyrównuje ćwierćobroty. Warstwa ukryta ma 48 neuronów, łącznie około 77 tysięcy parametrów. Implementacja NumPy wykorzystuje istniejące biblioteki; nie wymaga PyTorch, GPU ani pobierania modelu z internetu. Plik próbnego modelu miał 298 200 bajtów. `.ecmodel` przechowuje wagi i metadane w NPZ, wczytywanym bez pickle.

Uczenie używa ocenionych par i małych przesunięć wyłącznie w danych treningowych. Kolejny trening korzysta z całej bieżącej bazy uczącej, więc nie zależy od pamięci konkretnego procesu lub komputera. Baza i model są osobnymi zasobami: eksport modelu przenosi jego wyuczone wagi; eksport danych pozwala dalej trenować na drugim komputerze. Nie wdrożono automatycznej synchronizacji chmurowej.

Nowy domyślny tryb **Szybki + własny model**:

1. Geometria wektorowa i tekst PDF zbierają pewne propozycje.
2. Dotychczasowy matcher obrazu nadal obsługuje trudne/rastrowe obszary.
3. Niezależny, tańszy skan obrazu całej strony korzysta z ograniczonej rozdzielczości, 12 wariantów i cache obrazu. Pewne propozycje natywne nie są weryfikowane ponownie przez ten skan.
4. Mała sieć ocenia niepewne propozycje i rastrowe dopasowania. Odzyskany wyłącznie przez sieć kandydat trafia do weryfikacji i nie powiększa automatycznie licznika.
5. Oznaczenie urządzenia, kolor, profil i przestrzenne powiązanie z tekstem nadal rozstrzygają typ. Model nie może przypisać pewnego „10” do „7” ani „8”. Nieczytelne oznaczenie pozostaje do sprawdzenia.

Tryb ten nie ładuje DINO Base/Small i nie uruchamia nimi pełnostronicowego skanowania. Dotychczasowe pełne tryby są dostępne przez wybór trybu analizy. Bez własnych wytrenowanych wag działają geometria i obrazy; interfejs pokazuje **Szybki · zbieranie ocen**. Nie dostarczono losowych wag jako gotowego wytrenowanego modelu.

## Co znaczą statystyki

Panel porównuje geometrię obrazu, mały model i sumę ich propozycji na ocenionych wycinkach dokumentów testowych. Podaje poprawne pozytywne pary, pominięte pozytywne pary i fałszywe pozytywne pary, precyzję i wykrycie poprawnych par. Raport JSON rozbija wynik według dokumentu i grupy.

To test rozróżniania par, nie pomiar odszukania wszystkich opraw na całej stronie. Nie ma jeszcze pełnostronicowego benchmarku z kompletną ręczną prawdą referencyjną ani macierzy pomyłek wszystkich grup. Dodane ręcznie pominięcia są materiałem dla modelu, ale wynik 100% klasyfikacji wycinków nie oznacza 100% skuteczności lokalizacji urządzeń.

## Weryfikacja tej wersji

24 małe kontrole: 9 istniejących wzorca, 6 renderowania, 9 danych i uczenia. Zaliczone. Diagnostyka instalatora nowego trybu: PASS 12/12; zaznaczenie obejmujące opis zachowuje położenie symbolu także po obrocie. Nie uruchamiano historycznej pełnej regresji ani wszystkich modeli Base.

Sprawdzono:

- trwały zapis, korektę oceny, deduplikację, podział całych PDF-ów i eksport/import;
- rzeczywistą zmianę wag w treningu i identyczne predykcje po skopiowaniu modelu;
- odmowę treningu przy niepełnych lub wyłącznie niepewnych danych;
- zachowanie 8/8 natywnych opraw A1 w świeżym PDF-ie przy przejściu z klasycznego trybu na nowy; identyczny wynik semantyczny i brak załadowania dużego encodera;
- odzyskanie propozycji do weryfikacji bez automatycznego zliczenia i zachowanie innego oznaczenia QP14 poza grupą A1;
- zapis przez prawdziwy proces z kliknięcia Akceptuj, panel, Cofnij/Ponów i zmianę grupy;
- anulowanie treningu z zachowaniem danych, wcześniejszego modelu i oczekujących ocen.

Oddzielnie przeprowadzono cały przepływ z przycisku panelu: 60 syntetycznych ocen w czterech odłożonych zestawach, trening CPU, raport, aktywacja i ponowne wczytanie wag. Na 10 testowych parach: geometria obrazu 3 poprawne pozytywne / 5, 0 fałszywych; sieć 5/5, 0 fałszywych; suma propozycji 5/5, 0 fałszywych. Trening małej próby trwał około 0,21 s. 100 ocen par wraz z przygotowaniem obrazów trwało około 140 ms w tym Linux. Nie są to wyniki na dokumentacji użytkownika ani czas przeszukania strony.

## Ograniczenia i następny pomiar

Nie ma jeszcze rzeczywistej bazy ocen użytkownika, więc skuteczność wytrenowanego modelu na jego AW4 i rzutach 7–10 nie została potwierdzona. Pierwszy model należy ocenić na różnych rzeczywistych projektach. Mała sieć jest prostym początkiem, a nie obietnicą przewagi nad większą wyspecjalizowaną siecią.

Skan podglądu może pomijać bardzo drobne symbole; zgłasza ostrzeżenie, a geometria i lokalne ścieżki nadal działają. Przy nadmiarze podobnych propozycji zgłasza niepełne pokrycie. OCR lub klasyczny matcher na trudnej stronie wciąż może być kosztowny. Nie uruchamiamy w tle automatycznie wielominutowego Base. Ocenę szybkości i kompletności trzeba przeprowadzić na rzeczywistym PDF-ie, a odzyskane wyniki sprawdzić ręcznie.

Dane trafiają lokalnie do katalogu danych aplikacji, podfolder learning; użytkownik może wyeksportować je z panelu. Dokumentów i ocen nie wysyła się do GitHuba. W repozytorium jest wyłącznie kod oraz opis prób.
