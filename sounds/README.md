# Zvuky

Sem patří MP3 soubory, které se mají zabalit přímo do aplikace.

- Název tlačítka = název souboru bez přípony (podtržítka se nahradí mezerami).
  Např. `To_je_konec.mp3` → **To je konec**.
- Číslo na začátku názvu určuje pořadí a na tlačítku se nezobrazí:
  `05_Sad_trombone.mp3` → **Sad trombone**.
- Podporované formáty: mp3, ogg, wav, m4a, aac, flac.
- Nové soubory se při aktualizaci aplikace přidají na konec seznamu; vlastní
  pořadí a přejmenování nastavená v telefonu zůstanou zachována.

Současné zvuky jsou nahrávky z [Freesound.org](https://freesound.org) s volnou licencí
(CC0 / CC BY), autoři jsou v [`CREDITS.md`](../CREDITS.md). Vyrábí je
`tools/build_sounds.py` z kandidátů, které stáhne workflow *Fetch sound candidates*.
