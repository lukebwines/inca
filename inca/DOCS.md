# INCA

Gestionale degli affidamenti didattici per Home Assistant OS, Raspberry Pi aarch64 e amd64.
Il repository contiene esclusivamente codice e test sintetici, senza dati reali o credenziali.

## Funzioni

- Importazione del primo foglio di un report `.xls`; ogni caricamento valido sostituisce il report attivo.
- Archivio limitato ai codici corso MM? (tre caratteri), MM?? oppure M??R (quattro caratteri); filtri collegati, ricerca e selezioni multiple.
- Pratiche con originale conservato, proposta, storico, modifica ed eliminazione.
- Nove campi modificabili, oltre alle note della modifica: mutuazione, padre mutuazione, TAF, SSD, CFU, nome, cognome, totale ore e titolo affidamento.
- Excel `.xlsx` con CDS, anno accademico, i 17 campi concordati, saturazione premodifica, note e confronto deliberato/proposta, CSV, stampa PDF e backup ZIP.
- Utenti locali amministratori e operatori. Tutti condividono archivio e pratiche.

## Installazione e primo amministratore

1. Aggiungere `https://github.com/lukebwines/inca` allo store delle app/add-on di Home Assistant e installare o aggiornare INCA.
2. Mantenere `allowed_user` impostato al nome di accesso Home Assistant autorizzato (non il nome visualizzato).
3. Avviare INCA e aprire **Interfaccia web** da Home Assistant.
4. In **Utenti**, creare il primo account con ruolo **Amministratore** e password di almeno 12 caratteri.
5. Aggiungere gli altri amministratori o operatori. Non ci sono password predefinite né registrazione pubblica.

Gli amministratori gestiscono utenti, report e backup. Gli operatori consultano l'archivio,
creano/modificano/eliminano pratiche ed esportano i confronti. La disattivazione e il reset
della password invalidano tutte le sessioni dell'account. Non si può disattivare l'ultimo amministratore.
Il titolare di `allowed_user` può sempre gestire gli utenti attraverso Ingress, anche per il recupero delle password.

## Accesso dal tunnel: inca.archis.uk

Configurazione dell'add-on:

```yaml
allowed_user: "NOME_UTENTE_HOME_ASSISTANT"
external_enabled: true
external_host: "inca.archis.uk"
```

La porta interna **8100/tcp** del servizio con login viene pubblicata sulla porta **8108**
di Home Assistant. Se la porta è già occupata, cambiarla nella sezione Rete dell'add-on e
usare il valore scelto anche nel tunnel. La porta Ingress 8099 resta separata e non va esposta.

Nel tunnel già esistente aggiungere:

- Nome pubblico: `inca.archis.uk`
- Tipo di servizio: **HTTP**
- Destinazione: `http://IP_DI_HOME_ASSISTANT:8108` (sostituire il segnaposto con l'IP reale)
- Host HTTP inoltrato: `inca.archis.uk` (normalmente già preservato; se necessario impostarlo esplicitamente)

Accedere dal browser tramite **https://inca.archis.uk**. Il tratto interno dal tunnel al servizio
è HTTP; il browser usa HTTPS. I cookie di sessione sono Secure, HttpOnly e SameSite=Lax:
il login non è destinato all'accesso diretto via HTTP all'IP. Non occorre aprire porte sul router.
La creazione/configurazione del tunnel e del DNS è esterna al software e non è automatica.
Per disattivare il listener con login, impostare `external_enabled: false` e riavviare.

Ingress continua ad accettare solo il proxy Home Assistant con l'utente autorizzato.
Il servizio pubblico non considera attendibili gli header di identità Home Assistant.
Le password sono conservate come hash PBKDF2-SHA256 con sale individuale; le sessioni
scadono dopo otto ore e richiedono token CSRF per le operazioni. I tentativi di login sono limitati.

## Dati e backup

I dati persistono in `/data` durante riavvii e aggiornamenti. Le pratiche già salvate mantengono
gli originali anche dopo la sostituzione del report. I file non validi non sostituiscono l'archivio.
Gli account vengono creati sul dispositivo, non nel repository.

Il backup ZIP, riservato agli amministratori, contiene il database, gli hash degli account e il
report corrente; le sessioni sono escluse. Conservare il backup come documento riservato.
Il ripristino dello ZIP è manuale: fermare INCA, salvare una copia della situazione corrente,
ripristinare il contenuto della cartella `dati` in `/data`, senza sovrascrivere `options.json`,
poi riavviare. I backup Home Assistant dell'add-on conservano l'intera directory persistente.

## Limiti e verifiche

Nessun collegamento ai sistemi di Ateneo, nessuna approvazione o riconciliazione automatica
tra nuovi report e pratiche. Importazione `.xls` classica, non `.xlsx`. Le nuove coperture sono proposte derivanti da suddivisioni di ore di lezione; nuovi affidamenti autonomi e revoche non sono ancora implementati.
Il cambio di nome/cognome non aggiorna matricola, codice fiscale o afferenza.

Test locali: `python -m unittest discover -s tests -v` e `node tests/test_filters.cjs`.
CI: test e build Docker. L'accesso attraverso il tunnel deve essere verificato sul dispositivo
una volta configurato il DNS. Non è possibile verificare il Raspberry dalla suite locale.
Per sviluppo locale: `INCA_DATA=/percorso/temporaneo INCA_PORT=8099 python inca/app.py`.
In modalità locale il server ascolta solo su localhost; il listener esterno si avvia in modalità Ingress.
Il lettore xlrd è incluso in `inca/vendor` con la relativa licenza.

## Suddividere un incarico

Aprire la pratica e premere **Suddividi ore di lezione** sulla copertura originaria.
Verificare le ore di lezione attuali, inserire uno o più destinatari con le ore cedute e le note.
Il salvataggio riduce il totale e le ore di lezione del docente originario e crea nuove righe solo nella proposta.
I dati originali e la saturazione premodifica rimangono invariati. Il nome file Excel deriva dal titolo della pratica;
i caratteri non ammessi nei nomi file vengono sostituiti.

Nome, cognome e ore provengono dai dati inseriti. CFU, anagrafica e titolo non vengono dedotti dall'incarico originario:
i dati mancanti nelle nuove coperture sono indicati come **[DA VERIFICARE]** nell'Excel.
Verificare prima se i destinatari hanno già una copertura sullo stesso modulo, per evitare duplicazioni.
Le note di ciascuna riga sono modificabili insieme alla proposta; quelle generali restano in **Modifica titolo e note**.
Le note compaiono in Excel e PDF e possono descrivere coordinamento, decorrenza e adempimenti da verificare.

Il confronto mostra un controllo del totale per ciascuna suddivisione. Una successiva modifica delle ore può
creare temporaneamente una differenza: questa viene segnalata anche negli output, senza correggere automaticamente
le ore degli altri docenti. Per le righe coinvolte in una suddivisione, modificare il totale aggiorna le ore di lezione.

### Formato Excel (0.3.1)

Titolo della pratica, intestazioni blu scuro e sezioni separate. Ambra indica i dati modificati, verde chiaro le nuove coperture e rosso chiaro i dati da verificare. Le note hanno una colonna ampia; le righe si adattano al contenuto. Intestazioni e prime due colonne restano visibili durante lo scorrimento. Stampa A3 orizzontale all’80%, anche su più pagine in larghezza, con CDS e anno accademico ripetuti per orientarsi. Il formato non modifica i dati della pratica; riesportare per ottenere il nuovo stile.
