# INCA

Add-on personale per Home Assistant OS: importazione delle coperture didattiche,
filtri, pratiche di variazione e confronto deliberato/proposta.

## Stato

Prima versione 0.1.0. Codice predisposto per Raspberry Pi aarch64 e amd64.
Il collaudo reale su Home Assistant OS e la build del container sono ancora da eseguire.
Il repository contiene esclusivamente codice e test sintetici: nessun archivio reale,
nessun docente precompilato e nessuna credenziale.

## Funzioni

- Importazione del primo foglio di un Excel classico `.xls` con intestazioni compatibili.
- Filtri combinati e selezione multipla degli incarichi.
- Pratiche indipendenti con originale immutabile, proposta e storico dei salvataggi.
- Modifica docente, CFU, ore, titolo affidamento, periodo, note e mutuazione.
- Uscita dalla mutuazione con campi da completare esplicitamente.
- CSV per Excel, stampa PDF dal browser e backup ZIP scaricabile.
- Dati persistenti in `/data`, separati dal codice dell'add-on.

## Accesso

L'interfaccia è disponibile esclusivamente tramite Ingress di Home Assistant.
Nessuna porta viene pubblicata sulla rete. Sono accettate solo richieste dal proxy
Ingress e con il nome utente Home Assistant configurato in `allowed_user`.
Prima di aprire l'interfaccia, impostare quel valore nelle opzioni dell'add-on:
è il nome di accesso, non il nome visualizzato. Se vuoto, l'accesso è negato.

## Installazione da repository pubblico

Dopo la pubblicazione su GitHub, aggiungere il repository
`https://github.com/lukebwines/inca` allo store degli add-on di Home Assistant.
Installare INCA, compilare `allowed_user` nelle opzioni, avviare e aprire
l'interfaccia web. Non è necessario installare programmi sul PC.

Il container viene costruito dal Supervisor sul dispositivo. Gli aggiornamenti
si distribuiscono incrementando `version` in `inca/config.yaml` e aggiornando
lo store. Verificare prima un backup e avviare l'aggiornamento dall'interfaccia.
Non cambia il contenuto di `/data`. La prima installazione richiede accesso
alla rete per scaricare l'immagine Python ufficiale.

## Backup e ripristino

Scaricare periodicamente il backup dall'interfaccia. Il backup contiene dati
personali e fonti Excel, quindi va conservato con le stesse cautele degli originali.
In Home Assistant includere INCA nei backup per conservare `/data`.
Il ripristino del backup scaricato dall'app è manuale: fermare INCA, conservare una
copia dei dati correnti, ripristinare i contenuti della cartella `dati` dello ZIP
nella directory persistente `/data`, quindi riavviare. Non sovrascrivere options.json.

## Limiti

Solo `.xls`, non `.xlsx`. Nessun collegamento a sistemi di Ateneo, nessuna approvazione,
nessun calcolo automatico dei carichi. Ogni nuova importazione è separata.
Le pratiche non vengono consolidate in una situazione vigente comune.
Nuovi affidamenti, revoche e suddivisione su più righe non sono ancora implementati.
Il programma conserva campi vuoti e segnala discordanze senza inventare valori.
Le assegnazioni reali vanno inserite da fonti verificate dopo importazione.

## Test

`python -m unittest discover -s tests -v`

Per lo sviluppo locale, con Python già disponibile:
`INCA_DATA=/percorso/temporaneo INCA_PORT=8099 python inca/app.py`.
In questo caso il server ascolta solo su localhost. Il container attiva Ingress.

Il lettore XLS xlrd è incluso in `inca/vendor` con la relativa licenza.

## Esportazione proposta Excel

Dalla pratica salvata scegliere **Scarica proposta Excel**. Il file .xlsx contiene DELIBERATO e PROPOSTA DI MODIFICA, con le colonne del secondo foglio del modello e le righe della pratica nello stesso ordine. Le celle modificate sono gialle. Le colonne nascoste del modello diventano visibili se modificate; eventuali campi aggiuntivi modificati (es. NOTE) sono accodati. L’esportazione usa i dati salvati e non modifica l’archivio.

## Filtri collegati

Ogni elenco si adatta agli altri filtri e alla ricerca libera. Il filtro corrente non limita le proprie alternative: puoi quindi aggiungere altre scelte. Le selezioni attive non vengono cancellate automaticamente; se una ricerca le rende incompatibili, restano visibili con la dicitura «nessuna corrispondenza» per poterle togliere. Azzera filtri ripristina tutti i valori.

## Sostituzione report (0.1.9)

Ogni caricamento valido sostituisce il report attivo, anche ricaricando lo stesso file. I report precedenti non sono più selezionabili. Sono conservate solo le righe originali necessarie alle pratiche salvate, insieme alle proposte e allo storico. Le pratiche non vengono ricollegate al nuovo report. Un file non valido o privo di righe lascia intatto il report precedente.
