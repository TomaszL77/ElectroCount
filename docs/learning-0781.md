# ElectroCount 0.7.8.1 — kolejka ocen i porównywanie samej grafiki

## Wszystkie pozycje Sprawdź

W menu **Uczenie → Uczenie AI** zaznacz **Zapisuj moje oceny**, a następnie kliknij **Dodaj wszystkie ze Sprawdź do oceny**. Przycisk zbiera nowe wykrycia ze statusem Sprawdź z całego otwartego projektu, ze wszystkich jego stron i grup. Pozycje muszą mieć dostępny wzorzec grupy i źródłowy PDF. Nie dodaje pozycji zatwierdzonych ani odrzuconych.

W tabeli pojawią się jako **Do oceny**. Wybierz wiersz, obejrzyj wycinki, wybierz **Poprawny / Błędny kształt / Inny wariant / Niepewny** i kliknij **Zmień ocenę**. Ponowne kliknięcie przycisku zbiorczego nie dubluje pozycji ani nie nadpisuje istniejących ocen. Zapis odbywa się w oddzielnym procesie, a odświeżanie tabeli jest ograniczone podczas większej kolejki.

Do oceny nie oznacza oceny użytkownika. Ten status, Niepewny i Inny wariant nie uczestniczą w treningu. Dodanie do kolejki nie zmienia zatwierdzenia ani ilości elementów w projekcie. Akceptowanie i odrzucanie na rysunku nadal zapisuje świadome oceny jak w 0.7.8. Dane zachowują eksport/import, a minimalne warunki treningu pozostają te same.

## Białe otoczenie wzorca

Oryginalny wycinek i współrzędne zaznaczenia pozostają zapisane 1:1, ze wszystkimi wybranymi fragmentami i kolorami. Podgląd ma dodatkową wersję PNG z przezroczystym białym tłem, bez zmiany granic obrazu. Nie wybieramy automatycznie jednego fragmentu symbolu.

Matcher obrazu i szybki skan porównują grafikę z maską wykluczającą zewnętrzny biały papier. Białe wnętrza zamkniętych figur nadal opisują ich budowę: pusty i wypełniony symbol nie stają się przez to identyczne. Ramka wykrycia obejmuje grafikę zamiast białego marginesu. Jej położenie uwzględnia przesunięcie symbolu w zaznaczeniu oraz skalę i obrót.

Nowy trening małej sieci używa deskryptorów bez pustych marginesów, z zachowaniem proporcji i wszystkich części grafiki. Model ma format `electrocount-pair-mlp-v2`. Modele z 0.7.8 (`v1`) nadal można wczytać: dla nich zachowano poprzednią interpretację wejścia, żeby nie zmieniać zachowania zapisanych wag. Aby skorzystać z nowego wejścia AI, wykonaj nowy trening na swojej bazie i aktywuj jego wynik. Na obu komputerach używaj aktualnej aplikacji przy przenoszeniu nowych modeli lub danych ze statusem Do oceny.

## Mocny kształt trafia do sprawdzenia

W domyślnym trybie Szybki + własny model dodano dodatkową ocenę konturów samej grafiki. Gdy klasyczna weryfikacja odrzuci propozycję, mocna zgodność kształtu może przywrócić ją jako **Sprawdź — podobny kształt**. Nie wystarczy sam procent matchera: wymagane są zgodne kontury, proporcje, pokrycie i wypełnienie. Odzyskane pozycje wymagają oceny przed zliczeniem.

Własna sieć nadal może odzyskiwać propozycje odrzucone przez geometrię. Wyraźnie inne oznaczenie, np. QP14 zamiast A1, pozostaje innym wariantem. Profile IP/EX/faz i powiązanie tekstu nadal są analizowane. Nie podwyższono automatycznych ilości na podstawie samego kształtu. Analiza DINO Base pozostaje opcjonalnym dotychczasowym trybem.

## Sprawdzenie

28 małych kontroli: dotychczasowe 24 oraz 4 kontrole nowej kolejki, tła, zgodności modeli i odzyskiwania kształtu. Test tła obejmuje też pełny świeży PDF rastrowy: dwa jednakowe symbole, dodatkowa linia na białym otoczeniu jednej kopii, zachowane zaznaczenie, poprawne ramki i oznaczenia. Obie kopie pozostają dostępne do sprawdzenia. To sprawdzenie działania, nie pomiar skuteczności na rzeczywistej dokumentacji użytkownika.

Diagnostyka nowego trybu: PASS 12/12. Testy uruchomiono poza Windows; instalacji na komputerze użytkownika nie wykonywano. Renderer kafelkowy z 0.7.7.2 pozostaje bez zmian.
