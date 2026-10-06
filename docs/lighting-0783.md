# 0.7.8.3 — oprawy bez oznaczeń i ramki CAD

Wypełnione ramki CAD mogą składać się z wielu osobnych trójkątów zapisanych w jednej ścieżce. Sprawdzanie zaznaczenia traktuje teraz osobne kontury oddzielnie. Nie łączy ich w jeden wielokąt z pozornym wypełnieniem wnętrza arkusza. Symbol zaznaczony w środku takiej ramki może zachować pełną geometrię wektorową.

Nowa opcja Ustawienia → Wzorzec bez oznaczenia: kształt i kolor (także menu grupy) włącza celowo wyszukiwanie symbolu bez wymagania kodu tekstowego. Jest przeznaczona np. dla opraw identyfikowanych tylko grafiką. Pełna analiza oznaczeń pozostaje trybem domyślnym. W trybie kształtu i koloru jawnie różniący się kolor geometrii nie jest zgodnym trafieniem; szare tło architektoniczne nie staje się czarną oprawą. Kolor wzorca wektorowego pochodzi z jego geometrii, nie ze średniej małego antyaliasowanego podglądu. Źródło LEGEND rozszerza dopuszczalną skalę geometrii i wyklucza sam wzorzec z ilości.

Panel przypomina, że pominięcie to poprawny przykład dodawany ręcznie. Błędny przykład oznacza wycinek niepasujący do wzorca. Trening wstępny nadal wymaga co najmniej 20 poprawnych i 20 błędnych przykładów w zbiorze Uczenie oraz 30 lokalizacji. Walidacja/Test nie są automatycznie przenoszone do uczenia. Samo gromadzenie ocen nie zmienia modelu: po treningu użytkownik aktywuje wybraną wersję.

W ilościach należy zachować rozróżnienie między kandydatami a zatwierdzonym zestawieniem. Zgodność kształtu nie stanowi dowodu, że suma w legendzie jest aktualna. Rozbieżne ilości pozostają do oceny, bez przycinania listy do oczekiwanej liczby. Przenośne modele i przykłady użytkownika są osobnymi prywatnymi pakietami, nie częścią repozytorium.
