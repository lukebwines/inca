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
