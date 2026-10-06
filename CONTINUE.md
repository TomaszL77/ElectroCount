# 0.7.8.3 — ramki z osobnych wypełnionych konturów i oprawy bez kodów

Podstawa: 0.7.8.2, commit e2dcd475782f85e3134505c28972eed952c51a0b. Nowy tryb kształtu i koloru jest jawnie włączany przez użytkownika; pełne rozróżnienie oznaczeń pozostaje domyślne. Szczegóły: docs/lighting-0783.md. Modele, dane ocen i PDF-y użytkownika pozostają poza repozytorium.

# 0.7.8.2 — klipy CAD, katalog gniazd, model wstępny

Podstawa: 0.7.8.1, commit 2f2bbf40fe9651b0171bc33fcdc44db2faceb53e. Szczegóły: docs/sockets-0782.md. socket_symbols.py nie zawiera współrzędnych ani nazw dokumentów. Katalog użytkownika pochodzi z legendy projektu; zamknięte/sieciowe symbole wymagają jawnego socket_kind w sygnaturze. Domyślnie rozpoznawany jest tylko charakterystyczny korpus półkolisty. Model wstępny rozdziela fizyczne lokalizacje, a nie udaje niezależnych PDF-ów. Wycinki, modele użytkownika i dokumenty nie należą do repozytorium.

# 0.7.8.1 — kolejka Sprawdź, bez białego otoczenia, mocniejsze kształty

Podstawa: 0.7.8, commit 83c8bcc3d8aff4c4b70445733a8efbf0b53db31f. Dodano przycisk zbiorczego dodania wszystkich nowych review z projektu do bazy jako pending (Do oceny), bez nadpisywania istniejących ocen lub treningu na nieocenionych przykładach. Zapis pozostaje w osobnym procesie; odświeżenia tabeli są grupowane.

Oryginalne zaznaczenie zachowane 1:1. Nowy foreground.py maskuje zewnętrzny biały papier, zachowując wewnętrzne puste obszary figur. Matcher i szybki skan używają maski; ramki obejmują grafikę i prawidłowo zachowują jej przesunięcie po obrocie. Podgląd ma dodatkowy PNG RGBA. Test źródła porównuje ramkę grafiki, nie papieru.

Model v2 normalizuje puste marginesy, zachowując proporcje. Model v1 nadal wczytywany z poprzednim przetwarzaniem; do nowego wejścia użytkownik powinien ponownie wytrenować i aktywować model. Fast może odzyskać zgodny kontur po nieudanej weryfikacji ORB wyłącznie do REVIEW; inne oznaczenia i profile nadal obowiązują. Nie deklarować gotowych wag ani skuteczności na rzeczywistych schematach.

Sprawdzenie: 28 małych kontroli, diagnostyka PASS 12/12, syntetyczny PDF rastrowy z zewnętrzną linią: obie kopie dostępne do sprawdzenia, poprawne ramki i A1. Opis obsługi i ograniczeń: docs/learning-0781.md. Renderer zachowany bez zmian.

# 0.7.8 — zbieranie ocen i własny mały model

Użytkownik potwierdził poprawę renderowania w 0.7.7.2 i zlecił panel/model oraz wcześniejsze zmiany wyszukiwania. Podstawa: d3fee3f3635d310820215b3ef1897e4aac671912. Renderer pozostaje zachowany.

LearningStore zapisuje wyłącznie świadome oceny, LearningService/LearningWorker zbierają je w osobnym procesie i trenują TinyPairModel. Rzeczywista mała sieć NumPy ma około 77 tys. parametrów. Model i dane są przenośne. Panel Uczenie AI ma podział całych PDF-ów, porównanie na odłożonych parach, eksport/import, historię modeli i przerwanie treningu. Nie ma jeszcze danych rzeczywistych użytkownika ani dostarczonych gotowych wag; model powstaje z jego ocen. Minimum 60 ocen z 4 PDF-ów, zgodnie z warunkami readiness(). Niepewne i inne oznaczenia nie uczą geometrii. Cofanie/reassign nie utrwala błędnej grupy.

Domyślny tryb `learned` zastąpił domyślny Base. DINO nadal jest do wyboru w pełnych trybach. OCR nie ładuje DINO podczas tworzenia wzorca w nowym trybie. Dodano niezależny, ograniczony skan podglądu z cache. Mała sieć może odzyskać kandydatów odrzuconych przez geometrię obrazu, wyłącznie do kontroli. Dokładny tekst, kolor, profil i konflikty nadal obowiązują. Nie deklarować zachowania pełnej skuteczności Base na wszystkich projektach bez porównania rzeczywistych dokumentów.

24 małe kontrole PASS (9 wzorca, 6 renderowania, 9 uczenia). Przepływ panel → trening CPU → raport → aktywacja został sprawdzony osobno. 60 świeżych syntetycznych ocen, 10 testowych par: model 5/5 pozytywnych i 0 fałszywych. To test par, nie wynik na AW4/7–10 ani pełnym rzucie. Oryginalne dokumenty nie były obecnie dostępne. docs/learning-078.md zawiera ograniczenia i wyniki.

Następny krok: użytkownik zbiera rzeczywiste poprawne/błędne przykłady i ręczne pominięcia, trenuje z panelu i porównujemy rezultaty na odłożonych PDF-ach. Pełnostronicowa prawda referencyjna/macierze typów i mocniejszy model są dalszymi etapami. Instalator nie pobiera domyślnie Base; wykonuje diagnostykę nowego trybu. Nie wykonywano pełnej historycznej regresji ani instalacji Windows.

# 0.7.7.2 — renderowanie przed panelem uczenia

Podstawa: gałąź 0.7.7, commit 2ebe006d6421872d5d52cc249bdcd463d51acd14. Zmieniono wyłącznie wyświetlanie PDF i kolejkę podglądu. RenderService używa trwałego procesu render_worker, trzech aktywnych stron PDFium i cache kafelków. Rendering nie importuje detektora, OCR, ONNX ani modeli. viewport_tiles tworzy stałą siatkę 512 px, uwzględnia DPI i renderuje brzeg wokół widoku. DrawingView nie usuwa poprzednich kafelków przy przesunięciu. Kafelki mają margines renderowania dla poprawnego próbkowania skanów. Zaznaczanie i analiza pozostały zgodne z 0.7.7.1.

15 PASS: 9 kontroli wzorca i 6 renderowania; ograniczona, celowa weryfikacja. Nie wykonywano pełnej regresji detekcji. Benchmark identycznego fragmentu: mediana 250 ms → 18 ms w tym Linux; porównanie czterech świeżych kafelków, nie czasu całej strony lub wyszukiwania. docs/render-0772.md zawiera wyniki i ograniczenia.

Użytkownik chce najpierw ręcznie sprawdzić poprawę renderowania. Dopiero potem przechodzimy do zbierania ocen i panelu treningowego. Nie deklarować gotowego panelu, treningu ani przyspieszenia AI Base. Gałąź 0.7.7 pozostaje kopią 0.7.7.1; aktualizacja renderowania ma osobną gałąź 0.7.7.2.

# 0.7.7.1 — poprawka zapisu i podglądu zaznaczenia

Test rozpoznawania źródła jest diagnostyką: nie blokuje zapisania prawidłowego zaznaczenia. Nieudany test zostawia self_check=false oraz widoczne ostrzeżenie. Nie dodaje trafień do zliczenia. Oryginał nadal pochodzi dokładnie z selection_bbox, ma adaptacyjną rozdzielczość dla małych symboli. Podgląd zachowuje kolory i proporcje oraz wygładza skalowanie. Współrzędne myszy nie są zaokrąglane do całych pikseli przed przeliczeniem na PDF.

Weryfikacja: 9 PASS w tests/test_template_077.py; pikselowa zgodność RGB, prawdziwy mały symbol odrzucony przez lokalny matcher, zapis/odczyt JSON oraz przeciąganie przy trzech powiększeniach. Oryginalny PDF ze zrzutu użytkownika nie był dostępny; nie deklarować sprawdzenia go ani poprawy skuteczności wyszukiwania. Nie wykonywano pełnej regresji lub instalacji Windows.

# 0.7.7 — zakończony wyłącznie etap 1

Podstawa: feature/detection-0.7.6, commit 445967286a49f2f84132a231c52eb04dcfb425c0. Wersja 0.7.7 jest na osobnej gałęzi 0.7.7. Main pozostaje bez zmian.

Zachowano oryginalne zaznaczenie, wszystkie jego części i kolory. Oddzielono selection_bbox / symbol_bbox / matching_bbox / context_bbox. Oryginał RGB i podgląd odpowiadają selection_bbox. Dodano lokalny self-match przy tworzeniu i odtwarzaniu starego wzorca. Definicja wzorca 11.

Wykonano wyłącznie pięć małych kontroli nowego etapu. Wynik: 5 PASS; po małej korekcie zapisu diagnostycznego i integracji fallbacku ponowiono tylko dwie dotknięte kontrole: 2 PASS. Nie wykonywać pełnej regresji ani interpretować starych raportów jako potwierdzenia 0.7.7. Domyślny pytest wskazuje tests/test_template_077.py. Pozostała infrastruktura testowa jest historyczna; część dawnych plików wejściowych została usunięta na życzenie użytkownika.

Szczegóły zmian i porządków: docs/template-077.md. Prywatne dokumenty, stare projekty i wcześniejsze wersje poza tą gałęzią nie zostały zmienione. Kolejny etap wolno rozpocząć dopiero po wyniku ręcznych testów użytkownika.
