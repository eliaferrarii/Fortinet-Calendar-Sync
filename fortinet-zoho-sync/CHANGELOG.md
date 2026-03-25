# Changelog

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
