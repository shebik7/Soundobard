# Soundboard

Minimalistický soundboard pro Android (testováno pro Google Pixel 6a).
Mřížka tlačítek s názvy hlášek, klepnutím se zvuk přehraje, dalším klepnutím zastaví.

## Instalace do telefonu

1. Na telefonu otevři v prohlížeči stránku **Releases** tohoto repozitáře
   (`github.com/shebik7/Soundobard/releases`) a stáhni nejnovější `Soundboard.apk`.
   Případně v záložce **Actions** otevři poslední běh a stáhni artefakt `Soundboard-apk` (je zazipovaný).
2. Otevři stažený soubor. Android se zeptá, jestli prohlížeči povolíš instalaci
   neznámých aplikací – povol.
3. Nainstaluj. Aktualizace se instalují stejně, přes starou verzi – vlastní zvuky
   a nastavení zůstanou zachované.

Play Protect může upozornit na neznámého vývojáře – zvol „Přesto nainstalovat“.

## Zvuky

- **Zabalené v aplikaci:** MP3 soubory ve složce [`sounds/`](sounds/). Název tlačítka je
  název souboru (podtržítka → mezery, číselný prefix `01_` jen určuje pořadí).
  Po přidání souborů se automaticky sestaví nové APK.
- Aktuálně je tam 21 ukázkových zvuků (bič, airhorn, vine boom, ba-dum-tss, sad trombone,
  porno-jazz „bow chicka wow wow“, saxofon…). Jsou vlastní, vygenerované skriptem
  [`tools/generate_demo_sounds.py`](tools/generate_demo_sounds.py).
- **Přidané v telefonu:** Nastavení → *Přidat zvuky z telefonu*, nebo v jiné aplikaci
  (WhatsApp, Soubory…) *Sdílet → Soundboard*.

## Nastavení

- přidání zvuků z telefonu,
- změna pořadí přetažením za úchyt ≡,
- přejmenování klepnutím na název,
- skrytí zvuků z aplikace / smazání přidaných zvuků,
- počet tlačítek vedle sebe (2 / 3 / 4, výchozí 3),
- přehrávání přes sebe (výchozí vypnuto – nový zvuk zastaví předchozí).

## Testy

Každý push spustí na GitHub Actions emulátor (Pixel 6, Android 14), nainstaluje release APK
a skriptem [`scripts/e2e.py`](scripts/e2e.py) proklikne všechna tlačítka (ověří, že se každý
zvuk opravdu přehraje), otestuje nastavení a uloží screenshoty jako artefakt `e2e-results`.
Release se publikuje jen když testy projdou.

## Technické

Kotlin + Jetpack Compose, minSdk 26. APK sestavuje GitHub Actions
(`.github/workflows/build.yml`). Podpisový klíč `keystore/soundboard.jks` je záměrně
v repozitáři, aby šly aktualizace instalovat přes předchozí verzi.

Lokální sestavení: `./gradlew assembleRelease` (vyžaduje Android SDK).
