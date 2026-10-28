# INCA

Gestionale degli affidamenti didattici per Home Assistant OS, Raspberry Pi aarch64 e amd64.
Il repository contiene esclusivamente codice e test sintetici, senza dati reali o credenziali.

## Funzioni

- Importazione del primo foglio di un report `.xls`; ogni caricamento valido sostituisce il report attivo.
- Archivio limitato ai codici corso MM? (tre caratteri), MM?? oppure M??R (quattro caratteri); filtri collegati, ricerca e selezioni multiple.
- Pratiche con originale conservato, proposta, storico, modifica ed eliminazione.
- Nove campi modificabili: mutuazione, padre mutuazione, TAF, SSD, CFU, nome, cognome, totale ore e titolo affidamento.
- Excel `.xlsx` con i 17 campi concordati più la saturazione premodifica e confronto deliberato/proposta, CSV, stampa PDF e backup ZIP.
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
tra nuovi report e pratiche. Importazione `.xls` classica, non `.xlsx`. Nuovi affidamenti,
revoche e suddivisioni su più righe non sono ancora implementati.
Il cambio di nome/cognome non aggiorna matricola, codice fiscale o afferenza.

Test locali: `python -m unittest discover -s tests -v` e `node tests/test_filters.cjs`.
CI: test e build Docker. L'accesso attraverso il tunnel deve essere verificato sul dispositivo
una volta configurato il DNS. Non è possibile verificare il Raspberry dalla suite locale.
Per sviluppo locale: `INCA_DATA=/percorso/temporaneo INCA_PORT=8099 python inca/app.py`.
In modalità locale il server ascolta solo su localhost; il listener esterno si avvia in modalità Ingress.
Il lettore xlrd è incluso in `inca/vendor` con la relativa licenza.
