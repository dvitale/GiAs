# Problema: discrepanza eseguiti tra vw\_diff\_programmati\_eseguiti e vw\_cu

**Database**: `postgresql://mdgm\_owner:\*\*\*@10.200.16.119/mdgm` **Schema**: `chatbot` **Data analisi**: 2026-02-25


## Sintesi

La vista materializzata `chatbot.vw\_diff\_programmati\_eseguiti` restituisce **462 eseguiti** per la query:

```
SELECT sum(eseguiti) eseguiti FROM chatbot.vw\_diff\_programmati\_eseguiti  
WHERE descrizione\_uoc ILIKE '%IGIENE DEGLI ALLEVAMENTI E DELLE PRODUZIONI ZOOTECNICHE%'  
  AND anno = 2025 AND descrizione\_asl ILIKE '%benevento%' AND descrizione\_uos ILIKE '%IAPZ 1%';
```

Mentre la query diretta su `chatbot.vw\_cu` restituisce **624 eseguiti**:

```
SELECT sum(eseguiti) FROM chatbot.vw\_cu  
WHERE descrizione\_uoc ILIKE '%IGIENE DEGLI ALLEVAMENTI E DELLE PRODUZIONI ZOOTECNICHE%'  
  AND EXTRACT(YEAR FROM data\_inizio\_controllo) = 2025  
  AND descrizione\_asl ILIKE '%benevento%' AND descrizione\_uos ILIKE '%IAPZ 1%';
```

**Differenza**: 162 eseguiti persi.


## Causa

La vista `vw\_diff\_programmati\_eseguiti` parte dalle **programmazioni** (`vw\_programmazioni\_matrix`) e fa LEFT JOIN con i controlli (`vw\_cu`):

```
FROM chatbot.vw\_programmazioni\_matrix p  
LEFT JOIN chatbot.vw\_cu c  
  ON c.id\_indicatore = p.id\_indicatore AND c.id\_uos = p.id\_uos\_uoc\_asl
```

Per **22 indicatori**, la UOV IAPZ 1 (id `12619816`) ha eseguito controlli ma **non ha alcuna riga di programmazione** in `vw\_programmazioni\_matrix`. Quei controlli non sono programmati ma eseguiti dalla UOV IAPZ 1.

Poiche' la vista parte dal lato programmazioni, se per un indicatore non esiste riga con `id\_uos\_uoc\_asl = 12619816`, non c'e' nessuna riga a cui agganciare i controlli, e gli eseguiti si perdono.


## Dettaglio: i 22 indicatori senza programmazione sulla UOV IAPZ 1

Query di individuazione:

```
SELECT c.id\_indicatore, c.descrizione\_indicatore,  
       count(\*) as n\_controlli, sum(c.eseguiti) as tot\_eseguiti  
FROM chatbot.vw\_cu c  
WHERE c.id\_uos = 12619816   -- UOV IAPZ 1  
  AND EXTRACT(YEAR FROM c.data\_inizio\_controllo) = 2025  
  AND NOT EXISTS (  
    SELECT 1 FROM chatbot.vw\_programmazioni\_matrix p  
    WHERE p.id\_indicatore = c.id\_indicatore  
      AND p.id\_uos\_uoc\_asl = 12619816  
      AND p.livello\_struttura = 3  
      AND p.anno = 2025  
  )  
GROUP BY c.id\_indicatore, c.descrizione\_indicatore  
ORDER BY tot\_eseguiti DESC;
```

Risultato:

| id\_indicatore | indicatore | n\_controlli | tot\_eseguiti |
| - | - | - | - |
| 12240594 | B16\_A N. ISPEZIONI NEI CANILI | 23 | 23 |
| 12241083 | B36\_C Ispezioni in canili (ex Piano D6 benessere animale nei canili) | 23 | 23 |
| 12241209 | B16\_C Verifica requisiti strutture IUV L.3 | 23 | 23 |
| 12240660 | B51 N.ISPEZIONI NEI CANILI | 22 | 22 |
| 12241060 | b49\_e Ispezioni nei canili (controllo del 100% dei canili) | 22 | 22 |
| 12240817 | a39\_a N. campioni latte e prodotti lattiero-caseari | 10 | 10 |
| 12241029 | A41\_C campioni per la verifica dei criteri ex Reg CE 853/04 su latte crudo | 10 | 10 |
| 12241157 | A52\_AQ Campioni di latte bovino, bufalino e siero di latte per aflatossina | 5 | 5 |
| 12241212 | A41\_d Ispezioni per la verifica dei parametri del latte crudo | 4 | 4 |
| 12601243 | A1\_r Attivita' di disinfezione in corso di focolaio | 3 | 3 |
| 12240570 | ATT A3\_B SUPERVISIONE KNOW HOW PERSONALE | 2 | 2 |
| 12240654 | ATT\_AO7 N. ISPEZIONI | 2 | 2 |
| 12240819 | a41\_A Campioni verifica criteri microbiologici vendita latte crudo | 2 | 2 |
| 12241082 | a12\_x Campioni tab. 3.2 finalita' 3 (sorv. sostanze farmacologiche) | 2 | 2 |
| 12241189 | A62\_B Campioni di latte e derivati | 2 | 2 |
| 12240569 | ATT AO1\_A EFFETTUAZIONI DI N. ISPEZIONI | 1 | 1 |
| 12240571 | ATT A3\_A SUPERVISIONE SU CONTROLLI UFFICIALI | 1 | 1 |
| 12240621 | C13\_A N. CAMPIONI DI ALIMENTI DI O.A. | 1 | 1 |
| 12240735 | b15\_f Piano ad operativita' UVAC - Controlli intensificati | 1 | 1 |
| 12241190 | A62\_C campioni di uova fresche di gallina o altre specie | 1 | 1 |
| 12241191 | A62\_D campioni di miele | 1 | 1 |
| 12702924 | B55\_L Verifica documentale piani e manuali obbligatori | 1 | 1 |


**Totale: 22 indicatori, 162 eseguiti**


## Dettaglio controlli singoli eseguiti senza programmazione

```
SELECT c.id\_controllo, c.data\_inizio\_controllo, c.id\_indicatore,  
       c.descrizione\_indicatore, c.eseguiti, c.tecnica\_controllo,  
       c.ragione\_sociale  
FROM chatbot.vw\_cu c  
WHERE c.id\_uos = 12619816   -- UOV IAPZ 1  
  AND EXTRACT(YEAR FROM c.data\_inizio\_controllo) = 2025  
  AND NOT EXISTS (  
    SELECT 1 FROM chatbot.vw\_programmazioni\_matrix p  
    WHERE p.id\_indicatore = c.id\_indicatore  
      AND p.id\_uos\_uoc\_asl = 12619816  
      AND p.livello\_struttura = 3  
      AND p.anno = 2025  
  )  
ORDER BY c.data\_inizio\_controllo DESC;
```

Restituisce 162 righe con dettaglio di ogni singolo controllo.


## Soluzione: vista materializzata corretta

Creata `chatbot.vw\_diff\_programmati\_eseguiti\_x` che estende la vista originale aggiungendo i controlli eseguiti senza programmazione sulla stessa UOS:

```
CREATE MATERIALIZED VIEW chatbot.vw\_diff\_programmati\_eseguiti\_x AS  
  
-- Parte 1: programmazioni con eseguiti (identica alla vista originale)  
SELECT  
    p.alias\_indicatore AS indicatore,  
    p.descrizione\_indicatore,  
    aa.p\_descrizione AS descrizione\_asl,  
    aa.descrizione AS descrizione\_uoc,  
    p.descr\_uos\_uoc\_asl AS descrizione\_uos,  
    p.programmato AS programmati,  
    sum(COALESCE(c.eseguiti, 0::double precision)) AS eseguiti,  
    p.anno  
FROM chatbot.vw\_programmazioni\_matrix p  
LEFT JOIN chatbot.vw\_cu c  
    ON c.id\_indicatore = p.id\_indicatore AND c.id\_uos = p.id\_uos\_uoc\_asl  
JOIN matrix.vw\_tree\_nodes\_asl\_descr a ON a.id\_node = p.id\_uos\_uoc\_asl  
JOIN matrix.vw\_tree\_nodes\_asl\_descr aa ON a.p\_id = aa.id  
WHERE p.livello\_struttura = 3  
GROUP BY p.alias\_indicatore, p.descrizione\_indicatore, aa.p\_descrizione, aa.descrizione,  
         p.descr\_uos\_uoc\_asl, p.programmato, p.anno  
  
UNION ALL  
  
-- Parte 2: controlli eseguiti senza programmazione sulla stessa UOS  
SELECT  
    sp.alias AS indicatore,  
    c.descrizione\_indicatore,  
    c.descrizione\_asl,  
    c.descrizione\_uoc,  
    c.descrizione\_uos,  
    0::double precision AS programmati,  
    sum(c.eseguiti) AS eseguiti,  
    sp.anno  
FROM chatbot.vw\_cu c  
JOIN matrix.struttura\_piani sp ON sp.id = c.id\_indicatore  
WHERE NOT EXISTS (  
    SELECT 1 FROM chatbot.vw\_programmazioni\_matrix p  
    WHERE p.id\_indicatore = c.id\_indicatore  
      AND p.id\_uos\_uoc\_asl = c.id\_uos  
      AND p.livello\_struttura = 3  
)  
GROUP BY sp.alias, c.descrizione\_indicatore, c.descrizione\_asl, c.descrizione\_uoc,  
         c.descrizione\_uos, sp.anno;
```

Refresh:

```
REFRESH MATERIALIZED VIEW chatbot.vw\_diff\_programmati\_eseguiti\_x;
```


## Verifica

| Vista | Eseguiti |
| - | - |
| `vw\_diff\_programmati\_eseguiti` (originale) | **462** |
| `vw\_diff\_programmati\_eseguiti\_x` (corretta) | **624** |
| `vw\_cu` (query diretta) | **624** |


I controlli aggiunti dalla Parte 2 hanno `programmati = 0`, cosi' da distinguerli da quelli con programmazione regolare.

