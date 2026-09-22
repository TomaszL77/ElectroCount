# Weryfikacja 0.6

Pełny zestaw 70 PASS oraz dodatkowe testy diagnostyki. Testy GUI 100/125/150%, czysty runtime i sesja konta Windows użytkownika: 72 oprawy L3 + 1 legenda, jednakowe położenia. Szczegóły: [diagnostyka-06.md](diagnostyka-06.md).

Poniżej historyczne raporty wersji 0.5 i wcześniejszych.

# Walidacja ElectroCount 0.5 — 19.09.2026

**62 testy przeszły, 0 błędów i 0 pominiętych; 169,85 s.** Włączono pakiet rzeczywistych PDF i regresję dwóch sąsiednich L3. Po końcowym zwiększeniu czytelności cienkich znaczników ponowiono oba testy GUI: 2/2 przeszły w 9,12 s. Ponownie uruchomiono też okno hali i sprawdzono zapis/odczyt bez błędów. Aktualny wynik maszynowy: test-results.xml. Szczegóły nowego detektora, zakres oraz ograniczenia: [detekcja-05.md](detekcja-05.md).

Poniżej zachowano historyczny opis wersji 0.4; dane o dawnym limicie pełnej ekstrakcji nie opisują nowej drogi lokalnej.

---

# Walidacja ElectroCount 0.4 — 18.09.2026

**49 testów przeszło, 0 błędów, 0 pominiętych; 78,82 s.** Uruchomiono pełny zestaw z lokalnym folderem `AI trenig pack`. Wynik maszynowy: test-results.xml. Dodatkowe sprawdzenie po defensywnej zmianie obsługi pustych cech: 2/2 testy geometryczne przeszły.

## Zakres

- Odczyt/render/import PDF, wiele dokumentów, drag/drop przez rzeczywiste zdarzenia Qt.
- Dokładny odczyt QP14/A1, A1.1 bez fuzzy matching; oddzielne nakładające się obiekty tekstowe.
- QP14 = 4 i A1 = 8 na stronie 1 dostarczonego pliku demo, również po przejściu do rasteryzowanych kafelków.
- Takie same wyniki we wszystkich czterech profilach zasobów; fasada AI zachowuje wynik deterministycznego silnika.
- Weryfikacja geometryczna nie akceptuje samej ramki ani wzorca z brakującą przekątną. Linia tła przecinająca kompletny symbol jest dopuszczana tylko przy zgodnych, rozłożonych przestrzennie cechach i zachowaniu geometrii wzorca.
- Grupy, kolory, ukrywanie, konflikty, decyzje, ponowna analiza, Undo/Redo, anulowanie bez częściowego wyniku.
- Transakcyjny zapis i odczyt projektu, kopie źródeł z SHA-256, migracja v1, nowe sygnały AI opcjonalne w istniejących projektach.
- AUTO uwzględnia wolną pamięć i realne czasy, a nie nazwę GPU. Ustawienia są trwałe.
- Cache benchmarku jest unieważniany zmianą sprzętu; wolna pamięć odczytywana na nowo.
- Timeout profilera nie blokuje GUI. Brak modelu = pominięta inference, brak zmyślonego wyniku.
- OOM i błędy backendu obniżają profil z ograniczoną liczbą prób; błąd PDF nie uruchamia takiego ponawiania.
- ModelManager kontroluje SHA-256 i blokuje ścieżki wychodzące poza katalog wersji.
- ContextEngine i dataset pozostają nieaktywne; test potwierdza brak zapisu danych treningowych.

## Rzeczywiste pliki

| Plik | Strony | Teksty natywne | Sprawdzony zakres |
|---|---:|---:|---|
| rzut-testowy-demo.pdf | 2 | dostępne | Grupy QP14=4/A1=8, zliczanie, decyzje, zapis/odczyt |
| electrocount_test_advanced.pdf | 3 | dostępne | Import/nawigacja/render, kody A1/A11/A1.1/AI, kolizje tekstów |
| Instalacja odgromowa — garaż | 1 | 2380 pozycji | Import, render, natywny tekst/geometria, zapis projektu |
| Trasy kablowe — garaż — parter | 1 | 985 pozycji | Import, render, natywny tekst, limit geometrii, zapis projektu |
| E-01.pdf | 1 | 0 | Import, render, limit geometrii, zapis projektu |
| E-07.pdf | 1 | 0 | Import, render, limit geometrii, zapis projektu |

Pełne nazwy, sumy kontrolne i parametry stron: pakiet-testowy.json. Test GUI importuje cztery dokumenty do jednego projektu, odwiedza każdą stronę, sprawdza ręczną grupę/Undo/Redo, zapisuje i ponownie otwiera projekt z czterema źródłami. Ręczny element w tym teście jest kontrolą mechanizmu, nie adnotacją rzeczywistej instalacji.

Przed ograniczeniem E-01 zwracał 447 230 ścieżek, E-07 277 898. Szczyt working set procesu inspekcji całego pakietu wyniósł 1377,3 MB. Po ograniczeniu ekstrakcji: 242,8 MB. Czasy etapów wektorowych E-01/E-07 zmniejszyły się z około 42,6/37,1 s do 2,1/1,4 s. To pomiary tego komputera i tego przebiegu, nie gwarancja wydajności innych dokumentów.

Limit oznacza rezygnację z pełnego indeksu wektorowego na danej stronie i analizę rastra kafelkami. Zera `vector_paths` w takim raporcie nie oznaczają, że dokument nie zawiera wektorów. Nie wykorzystuje się częściowego indeksu jako pełnej informacji.

## Uruchomienie i kontrola wizualna

Uruchomiono natywne okno aplikacji, otwarto zapisany projekt z 2 stronami, 2 grupami i 12 wykryciami; brak błędów workerów. AUTO wybrał Eco przy około 781 MB wolnego RAM. Obejrzano rysunek i okno ustawień profilu. Dowody: uruchomienie.json, hardware-profile.json, podglad-ai.png i profil-sprzetu.png.

## Granice walidacji

Nowy pakiet nie ma zweryfikowanych referencyjnych liczności, dlatego nie przypisujemy mu precision/recall/F1 ani deklaracji poprawnego kosztorysu. Advanced PDF sprawdzono pod kątem importu i tekstów, nie pełnej skuteczności na każdym trudnym symbolu. E-01/E-07 zawierają widoczne napisy jako geometrię: bez przyszłego OCR nie można wiarygodnie odczytywać z nich kodów. Żaden plik z pakietu nie został użyty do treningu.

Nie uruchamiano neural/GPU inference, CUDA, WinML inference ani LightGlue z wagami; ich dostępność wykonawcza nie jest potwierdzona. CPU PDF/OpenCV jest rzeczywiście aktywne. Testy OOM/backendu są kontrolowanymi symulacjami, a nie celowym wyczerpywaniem pamięci komputera. Ręczne przeciąganie z Eksploratora na innej konfiguracji Windows pozostaje niezweryfikowane.
