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
