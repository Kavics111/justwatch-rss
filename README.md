# JustWatch → RSS (HU)

Nem hivatalos RSS-feed a magyar streaming-kínálat újdonságairól, a
[justwatch.com/hu/uj](https://www.justwatch.com/hu/uj) oldal adataiból.
A feedet GitHub Actions generálja ütemezetten, és GitHub Pages szolgálja ki
állandó URL-en, amire a NetNewsWire (vagy bármely RSS-olvasó) rá tud ülni.

Hogyan működik: a `generate_feed.py` lekérdezi a JustWatch belső GraphQL
API-ját (ugyanazt, amit maga a weboldal használ), és egy `rss.xml` fájlt ír ki.
Csak a Python standard library kell hozzá, nincs semmilyen függőség.

## Beüzemelés (kb. 5 perc)

1. **Hozz létre egy új, üres GitHub repót** (lehet privát is), pl.
   `justwatch-rss` néven, és töltsd fel bele ezt a 4 fájlt a mappaszerkezettel
   együtt:

   ```
   generate_feed.py
   index.html
   README.md
   .github/workflows/build.yml
   ```

2. **Kapcsold be a GitHub Pages-t a Actions forrással:**
   a repóban **Settings → Pages → Build and deployment → Source**:
   válaszd a **GitHub Actions** lehetőséget.

3. **Indítsd el a workflow-t kézzel** (vagy várd meg az ütemezést):
   **Actions** fül → *Build JustWatch RSS* → **Run workflow**.
   Lefutás után a Pages URL megjelenik a **Settings → Pages** alatt.

4. **A feed URL-je:**

   ```
   https://<felhasznalónév>.github.io/<repo-név>/rss.xml
   ```

   (A nyitólap, `index.html`, is mutatja ezt a linket.)

5. **NetNewsWire:** *File → New Feed*, illeszd be a fenti `rss.xml` URL-t.

## Testreszabás

A `generate_feed.py` tetején:

| Beállítás             | Mit csinál                                                    |
|-----------------------|---------------------------------------------------------------|
| `MAX_ITEMS`           | Hány tétel legyen a feedben (alap: 80).                        |
| `PROVIDER_ALLOWLIST`  | Ha kitöltöd, csak ezeknek a szolgáltatóknak az újdonságai jönnek be. Pl. `{"Netflix", "Max", "Disney Plus"}`. Üresen = minden. |
| `COUNTRY` / `LANGUAGE`| Másik ország/nyelv (pl. `"DE"` / `"de"`).                      |
| `POSTER_PROFILE`      | Poszterméret (`s166`, `s332`, `s592`).                        |

**Frissítési gyakoriság:** a `.github/workflows/build.yml`-ben a `cron`
sor szabja meg (alap: 6 óránként, UTC-ben). Pl. 3 óránként: `0 */3 * * *`.
Megjegyzés: a GitHub ütemezett futásai néha pár percet késhetnek, és
inaktív repóknál ~60 nap után felfüggesztheti az ütemezést — ilyenkor egy
push vagy kézi indítás újraindítja.

## Helyi teszt

```bash
# Éles lekérdezés (ha a géped eléri az apis.justwatch.com-ot):
python generate_feed.py --out rss.xml

# Offline teszt elmentett API-válaszból:
python generate_feed.py --mock-file sample.json --out rss.xml
```

## Jogi / technikai megjegyzés

Az adat a JustWatch-tól származik, ez a projekt a nyilvános belső API-ját
használja, személyes célra. Az API jelöletlen és előzetes értesítés nélkül
változhat; ha a feed egyszer csak üres lesz, valószínűleg a lekérdezés
(`QUERY`) mezőit kell igazítani a `generate_feed.py`-ban.
