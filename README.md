# ElectroCount 0.7.8 — własny mały model AI

Panel **Uczenie → Uczenie AI** zapisuje Twoje oceny, uruchamia lokalny trening i porównuje modele na odłożonych przykładach. Dane i modele można eksportować na drugi komputer. Zachowano ostre renderowanie kafelkowe i dokładny podgląd zaznaczenia z 0.7.7.2.

## Uruchomienie

Rozpakuj wersję do nowego folderu i uruchom **Uruchom.cmd z tego folderu**. W oknie musi być **0.7.8**. Jeśli działa runtime 0.7, nie musisz ponownie pobierać bibliotek ani dużego modelu. Przy pierwszej instalacji albo brakujących bibliotekach uruchom Instaluj.cmd. Instalator domyślnie nie pobiera DINO Base; Instaluj_AI.cmd pozostaje opcją dla pełnego, dotychczasowego trybu.

## Nauka podczas pracy

1. Otwórz PDF, zaznacz wzorzec i wyszukaj.
2. **Akceptuj** poprawne elementy, **Odrzuć** błędne kształty, **Dodaj ręcznie** pominięcia. Oceny zapisują się automatycznie.
3. Otwórz **Uczenie → Uczenie AI**, sprawdź wycinki i podział dokumentów.
4. Zbierz przykłady z co najmniej czterech PDF-ów. Panel pokazuje, czego jeszcze brakuje do treningu.
5. Kliknij **Wytrenuj model**, obejrzyj wynik i wybierz **Użyj tego modelu**.

Pierwsza baza jest pusta. Model nauczy się na Twoich ocenach; aplikacja nie dostarcza losowych wag jako gotowej wiedzy. Minimum do pierwszej próby: 20 poprawnych + 20 błędnych do uczenia z dwóch PDF-ów, 5 + 5 do walidacji z osobnego PDF-u i 5 + 5 do testu z kolejnego. Oceny „inny wariant” i „niepewny” pozostają zapisane, ale nie uczą geometrii.

## Wyszukiwanie i wyniki

Domyślnie działa **Szybki + własny model**: geometria, tekst, matcher obrazu, tańszy skan podglądu i wytrenowana mała sieć dla kandydatów. Nie uruchamia pełnostronicowego DINO Base. Bez własnych wag działa szybka część geometryczna i obrazowa. Pewne inne oznaczenie nadal wyklucza przypisanie do szukanej grupy. Odzyskane wyłącznie przez małą sieć elementy wymagają sprawdzenia przed zliczeniem.

Statystyki treningu mierzą ocenione pary wycinków, nie odnalezienie wszystkich opraw na całej stronie. Skuteczność na realnej dokumentacji wymaga dalszych pomiarów. Testy tej wersji: **24 zaliczone** oraz przepływ treningu z panelu na świeżych syntetycznych przykładach. Testy.cmd uruchamia mały zestaw wzorca, renderowania i uczenia; nie wszystkie historyczne testy.

[Instrukcja i raport uczenia](docs/learning-078.md) · [Raport renderowania](docs/render-0772.md) · [Dalsza praca](CONTINUE.md) · [Drugi komputer](START-TUTAJ.md)
