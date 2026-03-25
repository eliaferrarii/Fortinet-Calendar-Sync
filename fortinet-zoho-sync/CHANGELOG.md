# Changelog

## [1.1.14] - 2026-03-25

### Fixed
- Aggiunto un registro locale persistente degli eventi gia' creati o rilevati per bloccare duplicati anche quando la ricerca Zoho fallisce con HTTP 400

## [1.1.13] - 2026-03-25

### Fixed
- Deduplica resa conservativa: se esiste gia' un evento per lo stesso seriale nella stessa data, la sync non ne crea altri

## [1.1.12] - 2026-03-25

### Fixed
- Spostata la configurazione utente persistita su `/config/fortinet_zoho_sync_user_config.json` per evitare reset dopo update dell'add-on
- Mantenuta compatibilita' con il vecchio file legacy in `/data/user_config.json`

## [1.1.11] - 2026-03-25

### Fixed
- Se Zoho rifiuta `LkpAttivitaInterna`, la creazione evento viene ritentata senza quel lookup
- Se il report Zoho mostra gia' tanti eventi quanti sono i tecnici configurati, la sync evita nuove creazioni duplicate

## [1.1.10] - 2026-03-25

### Fixed
- Rafforzato il controllo duplicati con una seconda ricerca Zoho di fallback per titolo e seriale
- Aggiunti log espliciti sul numero di candidati trovati e sul motivo del match o mancato match
- Abilitato un fallback sicuro sul tecnico quando in configurazione c'è un solo tecnico ma Zoho non restituisce il lookup ID

## [1.1.9] - 2026-03-25

### Fixed
- Corretto il rilevamento dei duplicati sul calendario Zoho
- Normalizzato il confronto di data, ora e tecnico per evitare creazioni ripetute degli stessi eventi
- Allineato il controllo duplicati allo slot orario configurato invece di usare un valore fisso

## [1.0.6] - 2026-02-09

### Fixed
- Repository structure aligned to standard add-on layout
- Removed `webui` to avoid ingress URL issues
- Slug aligned with folder name to avoid ingress token issues
- Re-enabled ingress (fix "app does not support ingress")

## [1.0.0] - 2026-02-08

### Added
- 🎉 Prima versione dell'add-on
- ✅ Sincronizzazione automatica scadenze firewall Fortinet con Zoho Calendar
- ✅ Dashboard moderna per visualizzazione scadenze
- ✅ Supporto multipli tecnici
- ✅ Filtro giorni configurabile
- ✅ Rilevamento automatico duplicati
- ✅ API REST per integrazione con Home Assistant
- ✅ Esclusione automatica FortiAP, FortiSwitch e altri dispositivi non-firewall
- ✅ Spostamento automatico eventi weekend al venerdì
- ✅ Cache token Zoho per performance ottimali

### Features
- Ingress per accesso sicuro alla dashboard
- Health check endpoint per monitoring
- Log dettagliati per debugging
- Configurazione completa tramite UI Home Assistant
