# 0.7.8.5 — odtworzenie wyszukiwania z legendy

Podstawa: 0.7.8.4, commit 759a6490c20e5f933ed38bd49893b9a95bc1af7e.

## Przyczyna wyniku ograniczonego do wzorca

Na rzeczywistym nowym PDF odtworzono zwykłe zaznaczenie symbolu L2 z legendy.
Po dołączeniu kilku lokalnych wyników OCR rozpoznawanie tabeli było pomijane,
bo obecność jakiegokolwiek tekstu wyłączała analizę tabel wektorowych.
Wzorzec otrzymywał źródło DRAWING zamiast LEGEND.
Nazwa typu L2 została następnie potraktowana jako wymagany kod przy urządzeniu.
Na rzucie oprawy mają oznaczenia obwodów, a nie powtarzany podpis L2.
Wynik: 0 aparatów, jeden przykład z legendy, propozycje do sprawdzenia z brakiem kodu.

Poprzednie przygotowane projekty używały jawnego trybu kształtu i częściowo wzorców
z rzutu. Nie były dowodem sprawdzenia zwykłego zaznaczenia z legendy na innym PC.

## Zmiany

- Tabela symboli pozostaje legendą także po OCR. Ciągłość kolumn może składać się
  z krótkich kolejnych odcinków; nie trzeba jednego obiektu obejmującego kolumnę.
- Sam symbol wybrany w rozpoznanej tabeli domyślnie używa kształtu. Zewnętrzny
  podpis typu jest nazwą grupy, bez wymagania tego tekstu przy każdej oprawie.
  Kod świadomie objęty zaznaczeniem i jawne ustawienia pełnej analizy pozostają
  oddzielnym przypadkiem. Oryginalny RGB i wszystkie wybrane części są zachowane.
- Lokalny OCR nazwy obejmuje całą sąsiednią komórkę, z prawidłowym początkiem
  współrzędnych. Nie ucina końcówki L2-1 do L2-.
- Starsze zwykłe wzorce są odtwarzane przez definicję 12. Jawne ustawienia źródła
  i trybu są zachowywane.
- Po nieudanym dokładnym porównaniu można porównać równoważny zapis CAD:
  styczne odcinki połączone bez szczelin, pełne okręgi z innym podziałem krzywych
  oraz kropki zakończeń kresek. Oryginalna sygnatura nie jest zmieniana.
  Obszary wypełnienia, dodatkowe kreski i przerwy nadal rozróżniają warianty.
- Ukryty kontur PDF nie potwierdza widocznego symbolu: lokalny obraz sprawdza
  wypełnienie. Różny pełny/pusty obszar nie może zostać odzyskany samym wynikiem
  sieci. Inna widoczna struktura trafia do sprawdzenia. Przecinające tło można
  potwierdzić tylko przez ciągłą linię w obu marginesach poza aparatem.
- Kontury w zagnieżdżeniu mają naprzemienną rolę farby i pustki; wyspa farby
  wewnątrz otworu nie jest rzekomo wypełnionym otworem w identycznej parze.
- Mały model wymaga zgodnej struktury widocznej pary. Same wysokie wyniki sieci
  nie odzyskują izolowanych kropek ani jawnie innych wypełnień.
- Skan podglądu sprawdza rozmiar faktycznej grafiki, zamiast pustego marginesu.
  Zbyt drobne detale nadal analizuje dokładna geometria i lokalny obraz.
- Ustawienia → Eksportuj diagnozę wyszukiwania zapisuje wersję kodu, biblioteki,
  PDFium, hash PDF, zaznaczenie, tryb, rzeczywiście załadowany model i wynik.
  Raport zawiera wycinki wzorców; pełny PDF i wagi modelu nie są dołączane.
- Jednorazowy worker i test z menu zachowują faktyczną konfigurację modelu.
  Diagnostyka.cmd korzysta z domyślnego trybu learned, bez wymagania opcjonalnego Base.

## Sprawdzenie i ograniczenia

44 celowe kontrole regresji: zachowanie zaznaczenia i renderowania, uczenie,
serializacja, tabela po OCR, krótkie odcinki ramki, zagnieżdżone wypełnienie,
dodatkowa kreska/szczelina oraz eksport diagnozy. Zwykła ścieżka GUI obejmuje
import istniejącego modelu, świeże zaznaczenia L2/L2-1 z legendy nowego PDF,
wyszukiwanie przez worker, zapis projektu i eksport diagnozy.

Nie zmieniono wag poprzedniego modelu. Nowy dokument jest sprawdzeniem działania
detektora; liczby kandydatów nie stanowią kompletnego, zatwierdzonego przedmiaru.
Nie wykonywano instalacji ani testu GUI na komputerze użytkownika z Windows.
Porównanie jego rzeczywistych bibliotek wymaga wyeksportowanego raportu.
