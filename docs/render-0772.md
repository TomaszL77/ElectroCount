# ElectroCount 0.7.7.2 — renderowanie schematów

## Zachowanie przed i po

Poprzednia wersja czekała 220 ms od ostatniej zmiany przewijania. Dla każdego fragmentu uruchamiała electrocount.worker, importowała moduły analizy, otwierała PDF i zapisywała PNG. Ostry podgląd obejmował tylko jeden aktualny prostokąt. Podczas przesuwania nowy obszar korzystał z obrazu całej strony o ograniczonej jakości. Dodatkowy limit skali 4 i wymiaru 2400 px nie uwzględniał HiDPI ani większych powiększeń.

Nowa wersja:

- uruchamia osobny, trwały proces wyświetlania; PDFium działa poza GUI i poza procesem analizy;
- zachowuje do trzech otwartych stron z kontrolą rozmiaru i daty modyfikacji pliku;
- renderuje stałe kafelki 512 px, po jednym, z priorytetem aktualnego widoku;
- planuje pracę co najwyżej raz na 16 ms bez odkładania jej do zakończenia przeciągania;
- przechowuje ostre kafelki po przesunięciu i doczytuje pierścień sąsiednich kafelków;
- zastępuje nieaktualną kolejkę widoku, zachowując wynik pojedynczej pracy w toku;
- dopasowuje skalę do zoom × devicePixelRatio; nie używa dawnego limitu 4;
- używa czteropikselowego marginesu przy renderowaniu skanów i przycina go przed wyświetleniem; zapobiega zmianom próbkowania na krawędziach kafelków;
- nie przebudowuje wszystkich ramek wykryć podczas zwykłego przesuwania.

Cache serwisu ma limit 96 MiB. Widok usuwa stare kafelki po przekroczeniu 64 MiB, zachowując kafelki aktualnego planu; na bardzo dużych ekranach ich koszt może przekroczyć ten próg. QPixmap współdzieli dane pomiędzy cache a sceną. Podglądy całych stron mają osobny, istniejący limit sześciu stron. Proces renderuje maksymalnie jeden obraz naraz; pliki PNG są usuwane po wczytaniu. Cache obrazu nie jest bazą treningową.

## Mała weryfikacja

2026-10-05: `python -m pytest -q` — **15 PASS w 4,09 s**. Nie wykonywano pełnej regresji detektora.

- 9 dotychczasowych kontroli: dokładny prostokąt i RGB wzorca, mały symbol, ostrzeżenie bez blokady oraz zaznaczanie przy zoom 0,5 / 2 / 8.
- 6 nowych kontroli: klucze siatki przy przesuwaniu i HiDPI; kolory i geometria kafelków; ciągłe planowanie podczas ruchu; obrócony skan; stały proces, kasowanie kolejki i limit cache; okno aplikacji, powroty pomiędzy stronami i zoom 8.

Obraz wektorowy porównano z renderem całej strony w dwóch skalach na wszystkich 33 kafelkach zaplanowanych do testu. Wygładzanie PDFium po przesunięciu początku obrazu może różnić się maksymalnie o 2/255 w kanale; średnia różnica wynosiła poniżej 0,01. Obrócony skan po dodaniu marginesu był zgodny piksel po pikselu. Obejrzano również zrzut okna ze schematem przy zoom 4.

## Porównanie czasu

Świeży rysunek syntetyczny 1600,25 × 1000,75 pkt z tysiącami okręgów i linii. Cztery różne fragmenty 256 × 256 pkt, skala 2, wynik 512 × 512 px. Obie metody renderują tę samą jakość. Mierzono od wysłania zadania do odebrania rezultatu przez Qt, w tym narzut procesu. Serwis widoku uruchomiono przy starcie, tak jak w aplikacji. Pierwszy nowy kafelek obejmuje otwarcie strony; kolejne korzystają z tej samej strony. Stara metoda uruchamia proces dla każdego zadania.

| Fragment | Poprzedni proces | Stały proces | Pobranie z RAM |
|---|---:|---:|---:|
| 1 | 168,83 ms | 50,00 ms | 0,013 ms |
| 2 | 236,78 ms | 17,36 ms | 0,007 ms |
| 3 | 267,49 ms | 17,43 ms | 0,005 ms |
| 4 | 264,04 ms | 18,34 ms | 0,007 ms |
| Mediana | **250,41 ms** | **17,89 ms** | **0,007 ms** |

Skrypt: `PYTHONPATH=src QT_QPA_PLATFORM=offscreen python tools/benchmark_render_0772.py`. Wymaga dodatków testowych reportlab. Opcjonalny argument wskazuje własny PDF o stronie co najmniej 768 × 512 pkt. Plik użytkownika nie jest kopiowany do repozytorium.

To pomiar fragmentu w środowisku Linux, nie obietnica czternastokrotnie szybszej całej strony na Windows. Nowy obszar, szybki skok daleko na rysunku lub nowa skala nadal mogą korzystać krótko z podglądu, zanim powstaną nowe kafelki. Zbliżenie rastrowego skanu nie przywraca detali nieobecnych w źródle. Na bardzo złożonej stronie koszt PDFium nadal zależy od dokumentu. Nie było dostępnego oryginalnego PDF z ostatniego zgłoszenia użytkownika; potrzebna jest jego ręczna próba na komputerze roboczym.

Ta aktualizacja nie zmienia skuteczności ani czasu wyszukiwania przez AI Base. Panel ocen i treningowy jest kolejnym, uzgodnionym etapem po sprawdzeniu wyświetlania.
