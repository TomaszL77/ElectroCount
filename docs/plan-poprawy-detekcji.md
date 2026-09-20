> Aktualizacja 19.09.2026: wdrożony zakres i aktualne ograniczenia opisano w [detekcja-05.md](detekcja-05.md). Poniżej zachowano pierwotną diagnozę i propozycję z wersji 0.4.1.

# Propozycja naprawy detekcji na rzeczywistych rysunkach

## Co potwierdzono

Sprawdzono PDF „3525_30_HAL-A_IE_PT_00_201_Instalacja oświetlenia - hala cz.1”. Nie odtworzono dokładnego zaznaczenia użytkownika — aplikacja na zrzucie ma niezapisany stan, a sam zrzut nie zawiera współrzędnych wzorca.

W kontrolowanym wycinku tej samej strony znajdują się dwa sąsiednie elementy L3. Dla zaznaczenia o wysokości 36 punktów detektor zwrócił 2 trafienia. Zwiększenie wysokości do 46 punktów spowodowało utratę wiarygodnej etykiety oraz zwrócenie tylko 1 z 2 elementów. Przy wysokości 28 punktów pojawiały się dodatkowe nieprzypisane kandydaty. Wskazuje to na nadmierną zależność od otoczenia i granic prostokąta. Szczegóły: diagnoza-l3.json.

To nie jest pełny benchmark strony ani potwierdzenie całkowitej liczby opraw. Warstwa tekstowa zawiera 74 wystąpienia L3, ale część występuje poza właściwym obszarem instalacji / w opisach. Nie wolno utożsamiać liczby napisów z liczbą urządzeń.

## Przyczyny widoczne w kodzie i próbach

- Wzorzec rastrowy jest wycinany z całego zaznaczonego prostokąta. Fragmenty przewodu i drobne opisy zmieniają jego kształt oraz położenie środka.
- Maskowanie tekstu białym prostokątem może usuwać też geometrię leżącą pod napisem. Na tym PDF napis „117W” znajduje się na wąskim elemencie.
- Po przekroczeniu 40 000 segmentów strona traci całą ścieżkę dopasowania wektorowego. Ten PDF przekracza limit. Ochrona pamięci jest potrzebna, ale rezygnacja z lokalnej struktury dokumentu obniża jakość dopasowania.
- Stała skala rastra 2 px/punkt i ograniczone kąty (-8/0/+8 stopni) nie zapewniają obsługi różnorodnych symboli. Wektorowy matcher także odrzuca obroty większe od 12 stopni.
- Cienkie kreski i powtarzalne krawędzie są słabym materiałem dla ogólnego ORB/RANSAC. Samo zwiększenie DPI w próbie lokalnej nie poprawiło wyniku — weryfikator musi być dopasowany do typu geometrii.
- Tekst jest przypisywany po generowaniu i odrzuceniu kandydatów. Czytelne L3 nie pomaga odzyskać miejsca pominiętego wcześniej przez grafikę.
- Preferencja układu tekstu jest liczona w osiach strony, bez pełnej transformacji razem z obiektem. Role „kod oprawy”, „moc”, „obwód” są traktowane podobnie.
- Profile Eco/Maximum sterują obecnie zasobami. Nie zmieniają tych ograniczeń algorytmu.

## Rekomendowany zakres przebudowy

### 1. Najpierw poprawny wzorzec

Wprowadzić TemplateDefinition: osobna maska symbolu, obszar tekstu, orientacja, cechy geometryczne i otoczenie. Zaznaczenie służy wskazaniu obiektu, a nie bezpośrednio jako obraz do porównywania.

Rozdzielać grubą/wypełnioną oprawę od cienkiego przewodu na podstawie lokalnych obiektów PDF, szerokości kreski, wypełnienia i kontynuacji linii poza obiektem. Nie usuwać wszystkich długich linii — dla L3 sam symbol jest długi i cienki. Kolor może wspierać dopasowanie, ale nie może być jedynym kryterium.

Pokazać mały podgląd „co zostanie wyszukane”. Automatycznie sprawdzać, czy silnik odtwarza wskazany fragment. To test poprawności wzorca, nie automatyczne doliczenie pozycji z legendy. Gdy segmentacja jest niejednoznaczna, umożliwić korektę maski lub wskazanie drugiego egzemplarza.

### 2. Dwie uzupełniające się drogi wyszukiwania

Dla wzorca z czytelnym kodem: dokładne wystąpienia tekstu generują lokalizacje do sprawdzenia, a geometria potwierdza obecność symbolu. Nadal nie liczymy samego napisu.

Równolegle: kształt generuje kandydatów także tam, gdzie nie ma tekstu lub jest on nieczytelny. Tacy kandydaci mogą trafić do REVIEW. Obie ścieżki są łączone z deduplikacją i kontrolą konfliktów. Kod grupy pochodzi z zaznaczenia — bez listy klas na sztywno.

### 3. Lokalna geometria, orientacja i tekst

Zastąpić pełną listę szczegółowych ścieżek lekkim indeksem przestrzennym. Rozwijać dokładną geometrię tylko wokół wzorca i kandydatów. Zachować ograniczenia pamięci również na dużych stronach.

Dodać dopasowanie odcinków/konturów dla symboli ubogich w punkty charakterystyczne, niezależne od ORB. Rozpoznawać długość elementu i odróżniać całe urządzenie od pasującego fragmentu dłuższego urządzenia. Uwzględniać obroty 90/180/270 stopni i mniejsze odchylenia, transformując również oczekiwane położenie etykiety.

Renderować lokalne fragmenty z rozdzielczością dobraną do najcieńszej istotnej kreski, z budżetem pamięci. Większa rozdzielczość jest tylko jednym składnikiem; wynik weryfikować względem geometrii wzorca.

Oddzielić kody urządzeń od mocy i numerów obwodów. Ujednoznaczniać przypisanie symbol–tekst na podstawie sąsiedztwa wielu obiektów, zamiast izolowanego „najbliższego napisu”. Zachować dokładne porównanie kodów i wykluczanie legendy/tabel.

### 4. Mierzalne kryteria odbioru

Pierwszy test: dwa sąsiednie L3 muszą być odnajdywane z obu egzemplarzy jako wzorca, przy kilku marginesach zaznaczenia obejmujących kompletny symbol. L4 nie może zostać przypisane do L3.

Następnie przygotować ręcznie oznaczone wycinki z różnymi, wcześniej niewidzianymi wzorcami: oprawy, gniazda, czujki, symbole bez kodu, obrócone, cienkie, częściowo przykryte linią i obecne w legendzie. Zbiór ma obejmować różne projekty i sposoby eksportu PDF. Mierzyć precision/recall, pomylenie kodów i odsetek REVIEW. Rozdzielić wyniki „pominięty kandydat”, „odrzucony kształt” oraz „niepewny tekst”.

Nie deklarować skuteczności na dowolnym elemencie na podstawie liczby testów jednostkowych. Przypadki uszkodzone, nieczytelne lub nieodróżnialne muszą pozostać do weryfikacji; 100% skuteczności dla dowolnego PDF nie jest uczciwą obietnicą.

### 5. Model wizualny dopiero po ustaleniu bazy jakości

Enkoder może służyć jako dodatkowy sygnał podobieństwa i porządkować trudnych kandydatów. Nie zastąpi poprawnej maski ani dokładnego tekstu. Włączyć go dopiero, gdy kontrolowane porównanie pokaże poprawę na nowych projektach. Nie uruchamiać treningu ani VLM w ramach bieżącej poprawki paska postępu.

## Co zmieniono teraz

Duży panel nad rysunkiem: kontrastowa obwódka, szeroki pasek, procent, aktualna strona/etap, czas i widoczne anulowanie. Import/przygotowanie wzorca mają tryb nieokreślonego czasu zamiast udawanego procentu. Usunięto cofanie się raportowanego postępu między etapami. 17 testów związanych z importem, detekcją, zapisem i anulowaniem przeszło; zrobiono kontrolę wizualną panelu podczas rzeczywistej analizy.

Ta aktualizacja nie wdraża jeszcze opisanej przebudowy detektora. Zmiana panelu jest w wersji 0.4.1, widocznej po zapisaniu projektu i ponownym uruchomieniu.

## Podstawa techniczna kierunków do eksperymentów

[OpenCV Generalized Hough](https://docs.opencv.org/4.9.0/da/ddc/tutorial_generalized_hough_ballard_guil.html) dokumentuje wyszukiwanie wzorców kształtu z parametrami skali i obrotu — to jedna z metod do porównania, nie obietnica rozwiązania wszystkich cienkich symboli. [DINOv2](https://dinov2.metademolab.com/) pokazuje użycie cech do dense matching. Żaden z tych materiałów nie stanowi walidacji dokładności na tym rysunku instalacji; rekomendacja eksperymentów wynika z opisanej diagnozy.
