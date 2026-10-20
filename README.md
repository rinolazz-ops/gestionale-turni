# Gestione Turni – ACTV Extraurbano Sud

Strumento per riordinare la **numerazione dei turni**, **deposito per deposito**, in modo che
chiunque segua la sequenza (turno 14 → 15 → 16 …) non si trovi per più settimane consecutive a
fare la **stessa tipologia** di turno e non si trovi mai con una **pausa insufficiente** tra la
fine di una settimana e l’inizio della successiva.

Tutto gira in locale: niente internet, niente installazioni oltre a Python (usato solo per leggere
i PDF).

## File

| File | A cosa serve |
|---|---|
| `index.html` | la pagina da aprire nel browser (contiene già i dati) |
| `estrai_turni.py` | legge i PDF cartellini e aggiorna i dati della pagina |
| `turni.json` | i dati estratti (usato come copia di riserva / per controllo) |

## Uso quotidiano

1. Fai doppio clic su **`index.html`** → si apre nel browser.
2. Scegli il **deposito** con le schede in alto (Dolo, Cavarzere, Bojon, Padova, Fossò).
3. Premi **“⚡ Calcola questo deposito”** (oppure **“Calcola tutti i depositi”**): in un paio di
   secondi ottieni la proposta.
4. Nella sezione **4 · Simulazione** inserisci il numero di partenza e vedi settimana per settimana
   cosa si fa, con la pausa garantita’ verso la settimana dopo.
5. **“⬇ Scarica proposta (CSV)”** (tutti i depositi) per mandare la numerazione all’ufficio turni,
   **“🖨 Stampa”** per la copia di carta.

I dati nella pagina sono quelli estratti l’ultima volta; non c’è bisogno di ricaricare nulla.

## Aggiornare i dati (settimana successiva)

1. Scarica i nuovi PDF dei cartellini (Lun-Ven, Sabato, Festivo).
2. Da terminale, nella cartella del progetto:

   ```
   python -m pip install pypdf        # solo la prima volta
   python estrai_turni.py "C:\Downloads\qualcosa-LUN_VEN.pdf" "...\SABATO.pdf" "...\FESTIVO.pdf"
   ```

   Senza nomi di file lo cerca da solo in `Downloads` (file che contengono “TURNI”).
3. Riapri `index.html`: i turni nuovi sono già dentro.

Lo script riconosce il tipo di PDF dal nome (SABATO / FESTIVO / tutto il resto = Lun-Ven).

## I depositi

Il numero del turno indica il deposito di appartenenza (verificato sui cartellini dalla riga
“Monta …”):

| Numerazione | Depositò | Scritto nei cartellini |
|---|---|---|
| 1 – 54 | **Dolo** | `DEP.DOLO` / `DOLO.DEP` |
| 101 – 130 | **Cavarzere** | `DEP.CAV` |
| 201 – 225 | **Bojon** | `BOJON PK` |
| 301 – 311, 350 | **Padova** | `PD PARCH` |
| 501 – 508 | **Fossò** | `FOSSO'PK` / `FOS PK B` |
| 901, 902, 904 | **Jolly** (fuori turnazione) | `DEP.DOLO` |

**Ogni deposito gira per conto proprio**: la numerazione, le posizioni *disponibile* e
l’ottimizzazione sono separati, perché ogni autista appartiene a un solo deposito. Le soglie di
classificazione si possono impostare **per deposito** (o copiarle su tutti).

## Come vengono classificati i turni

| Categoria | Regola |
|---|---|
| **SPEZZATO** | due tratti orari (es. 07:00–09:30 + 14:02–18:48) |
| **PRIMO** (mattina) | comincia prima delle 11:00 **e** finisce entro le 14:00 |
| **TERZO** | comincia dalle 14:00 **oppure** finisce dopo le 21:00 (inclusi i notturni) |
| **SECONDO** | tutto il resto (praticamente da ora di pranzo a ora di cena) |
| **DISPONIBILE** | numero di turno **senza cartellino predeterminato**: il turno lo assegna l’ufficio turni in base alle esigenze (malattie, coperture,…) |
| **JOLLY** | turno breve (meno di 4 ore): **non entra nella turnazione**, è l’ufficio turni a assegnarlo nei giorni disponibili |

Le soglie si cambiano nel riquadro *“Classificazione dei turni”* e valgono per il deposito
selezionato (con “…e applica a tutti” per estenderle). Se un numero non ha il cartellino lun-ven
(per esempio il **15**, che esiste solo di festivo) lo strumento usa sabato/festivo e lo segnala
nella tabella. Cliccando su una categoria nella tabella sezione 5 la puoi **correggere a mano**.

## Come funziona la ricerca della numerazione

Ogni posizione `n` della sequenza corrisponde a una settimana: chi è alla posizione 14 questa
settimana la settimana dopo è alla 15, e arrivato all’ultimo si ricomincia dal 1 dello stesso
deposito. Le posizioni “disponibile” (es. 6, 11, 16 … a Dolo) sono i numeri **senza cartellino
predeterminato**: non è una settimana di riposo, è l’ufficio turni a decidere quel turno in base
alle esigenze del momento.

Lo strumento riordina i turni cercando di rispettare questo ordine “graduale”:

```
mattina/spezzato  →  secondo  →  terzo  →  (si ricomincia) mattina/spezzato …
```

Uno **spezzato** viene trattato come una mattina: **dopo uno spezzato meglio un secondo o un
terzo**, mai un altro mattina (il peso “Spezzato poi primo” è dedicato proprio a questo).

| Successione | Peso di default |
|---|---|
| stessa categoria ripetuta (es. spezzato → spezzato) | 100 |
| **spezzato → primo** (mattina su mattina) | 60 |
| stessa fascia (primo → spezzato) | 35 |
| inversione (secondo → primo, terzo → secondo) | 18 |
| salto (primo → terzo) | 28 |
| ciclo (terzo → primo) | 8 |
| disponibile a meno di 4 turni di distanza (per ogni turno mancante) | 40 |

### La distanza fra le settimane disponibile (regola dei 4 turni)

Fra un turno “disponibile” e il successivo devono passare, **quando possibile, almeno 4 turni
normali**, così i turni da assegnare restano ben distribuiti nel tempo. La regola vale sul ciclo
quindi anche dall’ultimo disponibile al primo (chiusura del giro).

Il menu *“Settimane disponibile”* decide come applicarla:

| Modalità | Comportamento |
|---|---|
| **automatico** (default) | i numeri disponibile restano dove sono **se già rispettano la regola** (Dolo, Cavarzere, Fossò) e vengono riequilibrati **solo dove non la rispettano** (Bojon) |
| **fissi alla posizione attuale** | non si toccano mai: le non conformità restano e vengono segnalate |
| **sempre liberi** | l’ottimizzatore può piazzarli dove preferisce, rispettando sempre ≥4 turni quando i numeri lo consentono |

Dove la regola è **matematicamente impossibile** lo strumento lo dice in rosso: a **Padova** con
4 disponibili su 12 posizioni servirebbero 16 turni normali ma i turni sono 8, quindi il massimo
realizzabile è 2 normali in mezzo (al limite del possibile: si segnala e basta).

Le statistiche **“Min turni prima di un disponibile”** e **“Disponibili con meno di 4 turni
prima”** confrontano numerazione attuale e proposta; le righe disponibile della tabella
riportano il conteggio dei turni normali che le precedono.

### La pausa di riposo (regola, non preferenza)

Tra la fine dell’ultimo servizio di una settimana e l’inizio del turno della settimana seguente
devono passare almeno **10 ore**, con deroga a **9h40**. Il calcolo considera:

* la fine di lun-ven (venerdì, anche se il turno finisce la mattina dopo),
* il sabato, se quel numero ha il cartellino sabato,
* la **domenica festivo**, se quel numero ha il cartellino festivo (settimana con festività) —
  è il caso più stretto: es. turno 1 festivo 16:25–23:55 seguito dal turno 4 che ricomincia
  lunedì alle 04:15.

L’ottimizzatore tratta queste pause come un vincolo **prioritario**: prima elimina le pause sotto
9h40, poi quelle tra 9h40 e 10h, e solo dopo migliora l’alternanza delle tipologie. Le eventuali
pause interne al singolo turno (lun-ven → sabato o sabato → festivo dello stesso numero, es.
D114, D125, D216, D501: ~11 ore) non dipendono dalla numerazione e finiscono nella sezione
**7 · Controlli pause interne** da verificare con l’ufficio.

Modalità dei disponibili e pesi si regolano nel riquadro *“Pesi della sequenza”*.

## Risultato con i cartellini di riferimento

| | Numerazione attuale | Numerazione proposta |
|---|---|---|
| Pause sotto 9h40 (tutti i depositi) | 2 (Dolo, Padova) | **0** |
| Pause sotto 10 ore | 2 | **0** |
| Settimane consecutive di stessa categoria | 18 | **4** |
| Inversioni | 16 | **14** |
| Disponibili con meno di 4 turni normali prima | 5 (Bojon 1, Padova 4) | **4** (solo Padova, impossibile) |
| Min turni prima di un disponibile | Bojon 2, Padova 1 | Bojon **5**, Padova 1 (minimo teorico) |
| Tempo di calcolo | — | ~2 s per tutti e 5 i depositi |

Dettaglio per deposito (proposta): **Dolo** 0 ripetizioni / 0 pause, disponibili invariati;
**Cavarzere** 1 ripetizione, disponibili invariati; **Bojon** 1 ripetizione, disponibili
rimossi da 205,208,213,218 a 205,211,217,223 (ora 5 turni normali fra uno e l’attivale);
**Padova** 0 ripetizioni, 4 disponibili ineliminabili; **Fossò** 2 ripetizioni, disponibile
invariato. Le ripetizioni residue non si possono azzerare con questi turni (per esempio a Fossò
ci sono 5 spezzati su 7 turni: con 3 sole posizioni di stacco due spezzati attaccati sono
matematicamente inevitabili).

Nota di realtà: su 110 numeri 56 sono turni spezzati e 24 primi, quindi più della metà dei turni
rientra nella fascia “mattina/spezzato”: qualche settimana mattina seguita da uno spezzato resta
inevitabile. Alzando o abbassando i pesi si sposta il compromesso fra ripetizioni, “primo poi
spezzato” e inversioni.

## Ipotesi fatte

* La numerazione è libera: i turni vengono riassegnati alle posizioni (il numero è solo un nome).
* Ogni deposito ha una sua ciclica indipendente (Dolo 1→54→1, Cavarzere 101→130→101, …).
* Il turno di lun-ven determina la tipologia della settimana; sabato e festivo dello stesso numero
  restano legati allo stesso turno (vengono spostati insieme).
* Le posizioni “disponibile” sono i numeri **senza cartellino predeterminato**: il turno lo
  assegna l’ufficio turni (malattie, coperture,…) e il suo orario qui **non è noto**, quindi nel
  controllo della pausa la catena si interrompe in quelle settimane.
* Nei controlli di pausa si considera il caso peggiore: una settimana qualunque, con l’eventuale
  festivo di domenica dello stesso numero.
* I numeri 901, 902, 904 sono turni brevi “jolly”: non fanno parte della rotazione.
