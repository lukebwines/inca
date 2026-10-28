# 0.2.2

- Archivio e filtri limitati ai codici corso di quattro caratteri MM?? oppure M??R.

# 0.2.1

- Corretto blocco iniziale del menu utenti: aggiunti gli elementi HTML richiesti dalla navigazione account.
- Test della navigazione su elementi effettivamente presenti nel documento.

# 0.2.0

- Login esterno multiutente per inca.archis.uk, con servizio separato su porta interna 8100 / host 8108.
- Gestione utenti da Home Assistant o amministratore INCA: creazione, disattivazione, reset password e cambio password personale.
- Ruoli amministratore/operatore su archivio condiviso; sessioni revocabili, password hash, controllo origine e CSRF, limite tentativi.
- Nessuna password predefinita; primo amministratore creato da Ingress. Backup applicativo senza sessioni.

# 0.1.13

- Rimosso il filtro Anno accademico e ripristinato Mutuazione nell’ordine del report.

# 0.1.12

- Rimosso il filtro Mutuazione e aggiunto Insegnamento.
- Filtri disposti secondo l’ordine delle colonne del report.

# 0.1.11

- Rimosso il filtro Scuola e aggiunto Modulo, con ricerca e selezione multipla collegata.

# 0.1.10

- Excel limitato ai 17 campi richiesti, tutti visibili, con blocchi prima/dopo.
- Modifica titolo e note delle pratiche; eliminazione con conferma, incluse proposte e storico.

# 0.1.9

- Ogni importazione sostituisce il report attivo e rimuove le vecchie righe non utilizzate nelle pratiche.
- Originali, proposte e storico delle pratiche conservati; importazioni non valide non sostituiscono l’archivio.

# 0.1.8

- Ricerca per lettere iniziali in ogni filtro, senza distinzione di maiuscole e accenti.
- Le ricerche negli elenchi mantengono le selezioni; azzeramento singolo e globale ripuliscono anche il testo.

# 0.1.7

- Archivio e filtri limitati ai codici corso M???; originali conservati integralmente.
- Nove campi modificabili: Mutuazione, Padre mutuazione, TAF, SSD, CFU, Nome, Cognome, Totale ore e Titolo affidamento.

# 0.1.6

- Filtri Cognome docente e Nome docente con selezione multipla, collegato agli altri filtri e alla ricerca libera.

# 0.1.5

- Filtri collegati: ogni elenco mostra i valori compatibili con gli altri filtri e la ricerca libera.
- Le selezioni multiple restano disponibili; le scelte già attive senza corrispondenze sono segnalate e possono essere rimosse.

# 0.1.4

- Esporta proposta Excel (.xlsx) con blocchi DELIBERATO e PROPOSTA DI MODIFICA, colonne del modello e celle modificate evidenziate.

# 0.1.3

- Selezione multipla con caselle in tutti i filtri; alternative nello stesso filtro e intersezione tra filtri.
- Riepilogo delle scelte, azzeramento singolo o globale e opzione Non compilato.

# 0.1.2

- Filtri Tipologia e Codice corso, con Sede corso già disponibile.
- Colonne Tipologia, Sede corso e Codice corso nell’elenco.
- Azzera filtri, riepilogo filtri attivi e messaggio per risultati vuoti.

# 0.1.1

- Corretto caricamento XLS attraverso Ingress: supporto richieste chunked e buffering del proxy.
- Controlli per file vuoti, upload incompleti e limite dimensione.
- Nessuna migrazione o cancellazione dei dati.

# 0.1.0

- Prima versione INCA per Home Assistant con accesso Ingress.
- Archivio XLS, filtri, proposte e confronto prima/dopo.
- Salvataggi persistenti, storico, backup e CSV.
- Limitazione al nome utente autorizzato e nessuna porta pubblicata.
- Nessun dato reale o caso nominativo incluso nei sorgenti.
