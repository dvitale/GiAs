# Problema: discrepanza eseguiti tra vw_diff_programmati_eseguiti e vw_cu

**Database**: `postgresql://mdgm_owner:***@10.200.16.119/mdgm`
**Schema**: `chatbot`
**Data analisi**: 2026-02-25

---

## Sintesi

La vista materializzata `chatbot.vw_diff_programmati_eseguiti` restituisce **462 eseguiti** per la query:

```sql
SELECT sum(eseguiti) eseguiti FROM chatbot.vw_diff_programmati_eseguiti
WHERE descrizione_uoc ILIKE '%IGIENE DEGLI ALLEVAMENTI E DELLE PRODUZIONI ZOOTECNICHE%'
  AND anno = 2025 AND descrizione_asl ILIKE '%benevento%' AND descrizione_uos ILIKE '%IAPZ 1%';
```

Mentre la query diretta su `chatbot.vw_cu` restituisce **624 eseguiti**:

```sql
SELECT sum(eseguiti) FROM chatbot.vw_cu
WHERE descrizione_uoc ILIKE '%IGIENE DEGLI ALLEVAMENTI E DELLE PRODUZIONI ZOOTECNICHE%'
  AND EXTRACT(YEAR FROM data_inizio_controllo) = 2025
  AND descrizione_asl ILIKE '%benevento%' AND descrizione_uos ILIKE '%IAPZ 1%';
```

**Differenza**: 162 eseguiti persi.

---

## Causa

La vista `vw_diff_programmati_eseguiti` parte dalle **programmazioni** (`vw_programmazioni_matrix`) e fa LEFT JOIN con i controlli (`vw_cu`):

```sql
FROM chatbot.vw_programmazioni_matrix p
LEFT JOIN chatbot.vw_cu c
  ON c.id_indicatore = p.id_indicatore AND c.id_uos = p.id_uos_uoc_asl
```

Per **22 indicatori**, la UOV IAPZ 1 (id `12619816`) ha eseguito controlli ma **non ha alcuna riga di programmazione** in `vw_programmazioni_matrix`. Quei controlli sono programmati sotto altre UOS (UOC IAPZ, UOSD IAPZ 60-63, UOV IAPZ 2, ecc.) ma eseguiti dalla UOV IAPZ 1.

Poiche' la vista parte dal lato programmazioni, se per un indicatore non esiste riga con `id_uos_uoc_asl = 12619816`, non c'e' nessuna riga a cui agganciare i controlli, e gli eseguiti si perdono.

---

## Dettaglio: i 22 indicatori senza programmazione sulla UOV IAPZ 1

Query di individuazione:

```sql
SELECT c.id_indicatore, c.descrizione_indicatore,
       count(*) as n_controlli, sum(c.eseguiti) as tot_eseguiti
FROM chatbot.vw_cu c
WHERE c.id_uos = 12619816   -- UOV IAPZ 1
  AND EXTRACT(YEAR FROM c.data_inizio_controllo) = 2025
  AND NOT EXISTS (
    SELECT 1 FROM chatbot.vw_programmazioni_matrix p
    WHERE p.id_indicatore = c.id_indicatore
      AND p.id_uos_uoc_asl = 12619816
      AND p.livello_struttura = 3
      AND p.anno = 2025
  )
GROUP BY c.id_indicatore, c.descrizione_indicatore
ORDER BY tot_eseguiti DESC;
```

Risultato:

| id_indicatore | indicatore | n_controlli | tot_eseguiti |
|---------------|------------|-------------|--------------|
| 12240594 | B16_A N. ISPEZIONI NEI CANILI | 23 | 23 |
| 12241083 | B36_C Ispezioni in canili (ex Piano D6 benessere animale nei canili) | 23 | 23 |
| 12241209 | B16_C Verifica requisiti strutture IUV L.3 | 23 | 23 |
| 12240660 | B51 N.ISPEZIONI NEI CANILI | 22 | 22 |
| 12241060 | b49_e Ispezioni nei canili (controllo del 100% dei canili) | 22 | 22 |
| 12240817 | a39_a N. campioni latte e prodotti lattiero-caseari | 10 | 10 |
| 12241029 | A41_C campioni per la verifica dei criteri ex Reg CE 853/04 su latte crudo | 10 | 10 |
| 12241157 | A52_AQ Campioni di latte bovino, bufalino e siero di latte per aflatossina | 5 | 5 |
| 12241212 | A41_d Ispezioni per la verifica dei parametri del latte crudo | 4 | 4 |
| 12601243 | A1_r Attivita' di disinfezione in corso di focolaio | 3 | 3 |
| 12240570 | ATT A3_B SUPERVISIONE KNOW HOW PERSONALE | 2 | 2 |
| 12240654 | ATT_AO7 N. ISPEZIONI | 2 | 2 |
| 12240819 | a41_A Campioni verifica criteri microbiologici vendita latte crudo | 2 | 2 |
| 12241082 | a12_x Campioni tab. 3.2 finalita' 3 (sorv. sostanze farmacologiche) | 2 | 2 |
| 12241189 | A62_B Campioni di latte e derivati | 2 | 2 |
| 12240569 | ATT AO1_A EFFETTUAZIONI DI N. ISPEZIONI | 1 | 1 |
| 12240571 | ATT A3_A SUPERVISIONE SU CONTROLLI UFFICIALI | 1 | 1 |
| 12240621 | C13_A N. CAMPIONI DI ALIMENTI DI O.A. | 1 | 1 |
| 12240735 | b15_f Piano ad operativita' UVAC - Controlli intensificati | 1 | 1 |
| 12241190 | A62_C campioni di uova fresche di gallina o altre specie | 1 | 1 |
| 12241191 | A62_D campioni di miele | 1 | 1 |
| 12702924 | B55_L Verifica documentale piani e manuali obbligatori | 1 | 1 |

**Totale: 22 indicatori, 162 eseguiti**

---

## Dettaglio controlli singoli eseguiti senza programmazione

```sql
SELECT c.id_controllo, c.data_inizio_controllo, c.id_indicatore,
       c.descrizione_indicatore, c.eseguiti, c.tecnica_controllo,
       c.ragione_sociale
FROM chatbot.vw_cu c
WHERE c.id_uos = 12619816   -- UOV IAPZ 1
  AND EXTRACT(YEAR FROM c.data_inizio_controllo) = 2025
  AND NOT EXISTS (
    SELECT 1 FROM chatbot.vw_programmazioni_matrix p
    WHERE p.id_indicatore = c.id_indicatore
      AND p.id_uos_uoc_asl = 12619816
      AND p.livello_struttura = 3
      AND p.anno = 2025
  )
ORDER BY c.data_inizio_controllo DESC;
```

Restituisce 162 righe con dettaglio di ogni singolo controllo.

---

## Soluzione: vista materializzata corretta

Creata `chatbot.vw_diff_programmati_eseguiti_x` che estende la vista originale aggiungendo i controlli eseguiti senza programmazione sulla stessa UOS:

```sql
CREATE MATERIALIZED VIEW chatbot.vw_diff_programmati_eseguiti_x AS

-- Parte 1: programmazioni con eseguiti (identica alla vista originale)
SELECT
    p.alias_indicatore AS indicatore,
    p.descrizione_indicatore,
    aa.p_descrizione AS descrizione_asl,
    aa.descrizione AS descrizione_uoc,
    p.descr_uos_uoc_asl AS descrizione_uos,
    p.programmato AS programmati,
    sum(COALESCE(c.eseguiti, 0::double precision)) AS eseguiti,
    p.anno
FROM chatbot.vw_programmazioni_matrix p
LEFT JOIN chatbot.vw_cu c
    ON c.id_indicatore = p.id_indicatore AND c.id_uos = p.id_uos_uoc_asl
JOIN matrix.vw_tree_nodes_asl_descr a ON a.id_node = p.id_uos_uoc_asl
JOIN matrix.vw_tree_nodes_asl_descr aa ON a.p_id = aa.id
WHERE p.livello_struttura = 3
GROUP BY p.alias_indicatore, p.descrizione_indicatore, aa.p_descrizione, aa.descrizione,
         p.descr_uos_uoc_asl, p.programmato, p.anno

UNION ALL

-- Parte 2: controlli eseguiti senza programmazione sulla stessa UOS
SELECT
    sp.alias AS indicatore,
    c.descrizione_indicatore,
    c.descrizione_asl,
    c.descrizione_uoc,
    c.descrizione_uos,
    0::double precision AS programmati,
    sum(c.eseguiti) AS eseguiti,
    sp.anno
FROM chatbot.vw_cu c
JOIN matrix.struttura_piani sp ON sp.id = c.id_indicatore
WHERE NOT EXISTS (
    SELECT 1 FROM chatbot.vw_programmazioni_matrix p
    WHERE p.id_indicatore = c.id_indicatore
      AND p.id_uos_uoc_asl = c.id_uos
      AND p.livello_struttura = 3
)
GROUP BY sp.alias, c.descrizione_indicatore, c.descrizione_asl, c.descrizione_uoc,
         c.descrizione_uos, sp.anno;
```

Refresh:

```sql
REFRESH MATERIALIZED VIEW chatbot.vw_diff_programmati_eseguiti_x;
```

---

## Verifica

| Vista | Eseguiti |
|-------|----------|
| `vw_diff_programmati_eseguiti` (originale) | **462** |
| `vw_diff_programmati_eseguiti_x` (corretta) | **624** |
| `vw_cu` (query diretta) | **624** |

I controlli aggiunti dalla Parte 2 hanno `programmati = 0`, cosi' da distinguerli da quelli con programmazione regolare.
