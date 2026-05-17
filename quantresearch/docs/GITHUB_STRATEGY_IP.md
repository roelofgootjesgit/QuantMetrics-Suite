# Strategy IP en GitHub

Dit project bevat research-artefacten, configs en metrieken die **concurrentieel gevoelig** kunnen zijn. Richtlijnen:

1. **Repository-visibility**  
   Houd de **canonical suite private** op GitHub als je geen strategische details met het publiek wilt delen. Dat is de enige harde garantie.

2. **Geen geheimen in git**  
   API-keys, broker-tokens en `.env` blijven buiten version control (zie `.gitignore`).

3. **Publieke mirror of open-source deelrepo**  
   Als je ooit een **publieke** variant wilt:
   - verwijder of anonimiseer **concrete performance-cijfers**, experiment-KPI’s en pad-namen naar productie-configs;
   - overweeg alleen **abstracte architectuur- en proces-docs** te spiegelen;
   - gebruik eventueel een **tweede remote** alleen voor die geschoonde branch.

4. **Issues / PR’s**  
   Geen live-orderlogica, broker-accountnamen of uitgewerkte edge-parameters in issues beschrijven als de repo publiek is.

De architecture-decisieregel in [`README.md`](../README.md) beschrijft alleen **welke lijn** gekozen is (Pad A), niet volledige strategie-implementatie — dat blijft in code + private runs.
