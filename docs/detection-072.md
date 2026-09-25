# ElectroCount 0.7.2 — poprawki wykrywania

Podstawa: GitHub main ac861db7f734b0485ed2853183e45507dfee7ad5 (0.7.1).

## Zmiany

- Łączenie współliniowych odcinków w obrębie jednej ścieżki PDF. Zachowane są przerwy, załamania, kierunek, krzywe, osobne obiekty i wypełnienie. Tolerancja 0,001 pt służy zaokrągleniom współrzędnych, nie upraszczaniu kształtu.
- Wzorce sprzed definition_version=7 są odtwarzane z oryginalnego zaznaczenia przy kolejnym wyszukiwaniu.
- W analizie rastrowej pełny symbol przecięty cienką poziomą lub pionową linią może zostać odzyskany, jeśli linia jest ciągła także w obu marginesach poza symbolem. Wszystkie dodatkowe piksele muszą należeć do tak potwierdzonej linii; zachowujemy cechy wzorca i ponawiamy ścisłą weryfikację.
- Sam wysoki wynik ORB nie usprawiedliwia już dodatkowej kreski. Bez dowodu ciągłości poza symbolem dodatkowa struktura pozostaje potencjalnym innym wariantem.
- Widoczny licznik Znaleziono (także wyniki bez przypisania), osobny licznik bieżącej strony, dodatkowa kolumna w grupach i filtr Na rysunku tylko aktywna grupa. Filtr nie usuwa wyników ani nie zmienia zliczeń. Lista wyników zawiera numer strony projektu.
- Test OCR korzysta z czcionki dostępnej także poza Windows; nadal uruchamia prawdziwe rozpoznawanie OCR.

## Odtworzone przypadki

| Przypadek kontrolny | 0.7.1 | 0.7.2 |
|---|---:|---:|
| Trzy identyczne urządzenia, różny podział prostych w eksporcie, wzorzec niesegmentowany | 1/3 | 3/3 |
| Ten sam test, wzorzec segmentowany | 2/3 | 3/3 |
| Raster: QP14, część opraw przecina ściana | 3/4 | 4/4 |
| Raster: rozpoznane pozostałe oprawy A1 w tym samym teście | 6/8 | 8/8 |

W testach podziału odcinków są również trzy niepasujące warianty: bez ramki, bez kreski wewnętrznej i z wypełnionym środkiem. Są odrzucane. Powtórzone uruchomienia dają ten sam hash wszystkich położeń i przypisań. Testy otoczenia obejmują obie orientacje linii, brak ciągłości poza symbolem i wypełniony wariant.

## AI

Zainstalowano i uruchomiono dotychczasowy przypięty DINOv2-small ONNX z kontrolą SHA-256. Porównanie na jednej syntetycznej stronie EW1: klasyczny 3/3, 0 fałszywych trafień, 0,223 s; hybrydowy 3/3, 0 fałszywych trafień, 3,960 s. Identyczny hash lokalizacji i etykiet. Pomiary obejmują inicjalizację i nie są benchmarkiem laptopów użytkownika. Model nie został zmieniony ani promowany na domyślny.

Większy DINOv2-B jest kandydatem do osobnego porównania, a nie potwierdzonym rozwiązaniem. Oficjalna karta modeli opisuje S/B/L/g jako ekstraktory cech, nie gotowy klasyfikator osprzętu: https://github.com/facebookresearch/dinov2/blob/main/MODEL_CARD.md . Potrzebne są oznaczone przykłady poprawnych symboli i podobnych wariantów z prawdziwych PDF; dopiero poprawa lokalizacji i rozróżniania typów uzasadnia zmianę.

## Ograniczenia

Pełna seria regresji: **149 PASS, 4 SKIP, 0 błędów (22,46 s)**. Wcześniejsza seria ujawniła zależność akceptacji dodatkowej kreski od obrotu; usunięto obejście ORB bez dowodu ciągłości w otoczeniu i test obu orientacji przechodzi. Test instalacyjny 12/12, import GUI, wyszukiwanie, grupy, anulowanie, zapis/odczyt oraz zgodność GUI/serwis są objęte regresjami.

Testy odbyły się na Linux/Python 3.12 z Qt offscreen, PDFium, OpenCV CPU, prawdziwym OCR i modelem ONNX. Nie wykonano instalacji na laptopie służbowym ani testu jego sterowników/skalowania ekranu. Zrzuty z maila nie zawierają oryginalnej struktury PDF. Prywatne pliki CPP203, hala i pakiet użytkownika nie były dostępne; dotyczące ich testy mają jawne pominięcia.

Nie potwierdzono poprawy konkretnych wyników ze zdjęć, pełnego rozróżniania EX ani poprawności wszystkich wariantów osprzętu. Ciężkie zasłonięcia, ukośne linie tła oraz inaczej podzielone krzywe/osobne obiekty mogą nadal powodować pominięcia. W Windows należy uruchomić Diagnostyka.cmd (oczekiwane 12/12), a następnie przeliczyć ten sam zapisany projekt na obu komputerach.
