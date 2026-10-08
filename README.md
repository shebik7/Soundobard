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
  název souboru (podtržítka → mezery). Po přidání souborů se automaticky sestaví nové APK.
- **Přidané v telefonu:** Nastavení → *Přidat zvuky z telefonu*, nebo v jiné aplikaci
  (WhatsApp, Soubory…) *Sdílet → Soundboard*.

## Nastavení

- přidání zvuků z telefonu,
- změna pořadí přetažením za úchyt ≡,
- přejmenování klepnutím na název,
- skrytí zvuků z aplikace / smazání přidaných zvuků,
- počet tlačítek vedle sebe (2 / 3 / 4, výchozí 3),
- přehrávání přes sebe (výchozí vypnuto – nový zvuk zastaví předchozí).

## Technické

Kotlin + Jetpack Compose, minSdk 26. APK sestavuje GitHub Actions
(`.github/workflows/build.yml`). Podpisový klíč `keystore/soundboard.jks` je záměrně
v repozitáři, aby šly aktualizace instalovat přes předchozí verzi.

Lokální sestavení: `./gradlew assembleRelease` (vyžaduje Android SDK).
