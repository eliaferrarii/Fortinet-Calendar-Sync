# Documentazione Tecnica

## Architettura

L'add-on è composto da 3 componenti principali:

### 1. Flask Web Server
- Porta: 8099
- Ingress abilitato per accesso sicuro
- Endpoints API REST
- Dashboard HTML moderna

### 2. Fortinet Sync Manager
- Carica dati dispositivi da JSON
- Filtra solo firewall FortiGate
- Calcola scadenze e date eventi
- Gestisce logica weekend

### 3. Zoho API Client
- Autenticazione OAuth2 con refresh token
- Cache token per performance
- Creazione eventi calendario
- Rilevamento duplicati

## Flusso Operativo

```
1. Caricamento Configurazione
   ↓
2. Lettura Dati Fortinet (/data/fortinet_devices.json)
   ↓
3. Filtro Dispositivi (solo firewall, giorni configurati)
   ↓
4. Calcolo Date Eventi (giorno prima, escluso weekend)
   ↓
5. Per ogni dispositivo e tecnico:
   - Controllo duplicato in calendario
   - Se non esiste: Crea evento
   ↓
6. Ritorna risultato
```

## File Structure

```
/
├── config.yaml                 # Configurazione add-on HA
├── Dockerfile                  # Container build
├── build.yaml                  # Multi-arch build config
├── README.md                   # Documentazione utente
├── DOCS.md                     # Documentazione tecnica
├── CHANGELOG.md                # Changelog versioni
└── rootfs/
    └── opt/fortinet-zoho-sync/
        ├── run.sh              # Entrypoint script
        ├── app.py              # Flask application
        ├── fortinet_sync.py    # Sync logic
        ├── zoho_api.py         # Zoho API client
        ├── requirements.txt    # Python dependencies
        └── templates/
            └── index.html      # Dashboard UI
```

## Dati Persistenti

L'add-on utilizza la directory `/data` per persistere:

- `/data/fortinet_devices.json` - Dati dispositivi Fortinet
- `/data/zoho_refresh_token.txt` - Refresh token Zoho (plaintext)
- `/data/zoho_tokens.json` - Cache access token (auto-generato)

## API Endpoints

### GET /api/devices
Ritorna lista dispositivi in scadenza.

**Response:**
```json
{
  "success": true,
  "count": 2,
  "devices": [
    {
      "serial": "FGT60FTK2109B1AL",
      "model": "FortiGate 60F",
      "description": "Firewall principale",
      "services": [...],
      "earliest_days": 16,
      "event_date_str": "2026-02-23"
    }
  ]
}
```

### POST /api/sync
Esegue sincronizzazione con calendario Zoho.

**Response:**
```json
{
  "success": true,
  "result": {
    "devices_found": 2,
    "events_created": 4,
    "events_skipped": 0,
    "events_failed": 0
  }
}
```

### GET /api/config
Ritorna configurazione corrente (senza client_secret).

### GET /api/health
Health check per monitoring.

## Configurazione Zoho

### Scopes Richiesti
```
ZohoCreator.meta.READ
ZohoCreator.report.READ
ZohoCreator.data.READ
ZohoCreator.data.WRITE
ZohoCreator.data.CREATE
```

### Endpoint Utilizzati

**Lettura Eventi (check duplicati):**
```
GET https://creator.zoho.{dc}/api/v2.1/{owner}/{app}/report/{report}
?criteria=Data = 'DD/MM/YYYY' && Titolo.contains("Scadenza") && Titolo.contains("SERIAL")
```

**Creazione Evento:**
```
POST https://creator.zoho.{dc}/api/v2.1/{owner}/{app}/form/{form}
{
  "data": {
    "Data": "DD/MM/YYYY",
    "DataInizio": "DD/MM/YYYY HH:MM",
    "DataFine": "DD/MM/YYYY HH:MM",
    "Titolo": "Scadenza MODEL - SERIAL",
    "DescrizioneAttivita": "...",
    "Tipologia": "Altre attività",
    "OrePianificate": 1.0,
    "LkpTecnico": ID_TECNICO,
    "LkpAttivitaInterna": ID_ATTIVITA_INTERNA,
    "Reparto": "IL_TUO_REPARTO"
  }
}
```

## Filtro Dispositivi

Il filtro dispositivi applica questi criteri in ordine:

1. **Tipo Dispositivo**: Solo FortiGate (modello contiene "FortiGate", inizia con "FGT" o "FG-")
2. **Range Giorni**: Scadenza tra `filter_days_min` e `filter_days_max`
3. **Raggruppamento**: Raggruppa servizi per serial number
4. **Data Evento**: Calcola giorno prima della scadenza più vicina
5. **Weekend**: Sposta al venerdì se cade sabato/domenica

## Rilevamento Duplicati

Un evento è considerato duplicato se:
1. Data uguale (`Data = 'DD/MM/YYYY'`)
2. Titolo contiene "Scadenza" E il seriale
3. Tecnico assegnato corretto (`LkpTecnico = ID`)
4. Orario 08:00-09:00 (`DataInizio = '08:00'`, `DataFine = '09:00'`)

Tutti e 4 i criteri devono essere soddisfatti.

## Multipli Tecnici

Se configuri più tecnici:
```yaml
technicians:
  - id: ID_TECNICO
    name: "Tecnico Esempio"
  - id: 168291000000123456
    name: "Mario Rossi"
```

Verrà creato UN evento separato per OGNI tecnico per OGNI dispositivo.

Esempio: 2 firewall in scadenza × 2 tecnici = 4 eventi totali.

## Performance

- Cache token Zoho: riduce chiamate auth (~1 ora di cache)
- Batch processing: elabora tutti i dispositivi in una singola run
- Filtro duplicati: evita chiamate API non necessarie
- Auto-refresh dashboard: ogni 5 minuti

## Security

- Token Zoho in file separato (non hardcoded)
- Client secret marcato come password in config
- Ingress HA per accesso sicuro
- Nessun dato sensibile nei log

## Troubleshooting

### Log Levels

I log seguono questo schema:
- `INFO`: Operazioni normali
- `WARNING`: Situazioni anomale ma gestibili
- `ERROR`: Errori che impediscono operazioni

### Debug

Per debugging dettagliato, modifica `app.py`:
```python
app.run(host='0.0.0.0', port=8099, debug=True)
```

### Common Issues

**"Zoho refresh token not found"**
- Soluzione: Crea `/data/zoho_refresh_token.txt`

**"Fortinet data file not found"**
- Soluzione: Crea `/data/fortinet_devices.json`

**"Permission denied"**
- Soluzione: Verifica scope OAuth Zoho

**"No records found"**
- Verifica: data corretta, seriale corretto, sintassi criteria

## Integrazioni Home Assistant

### Sensors

Puoi creare sensori custom:

```yaml
sensor:
  - platform: rest
    name: "Fortinet Scadenze Count"
    resource: "http://localhost:8099/api/devices"
    value_template: "{{ value_json.count }}"
    scan_interval: 3600
```

### Notifications

Invia notifiche quando ci sono scadenze urgenti:

```yaml
automation:
  - alias: "Notifica Scadenze Urgenti Fortinet"
    trigger:
      - platform: numeric_state
        entity_id: sensor.fortinet_scadenze_count
        above: 0
    action:
      - service: notify.mobile_app
        data:
          message: "Attenzione: {{ states('sensor.fortinet_scadenze_count') }} firewall in scadenza!"
```

## Contribuire

Per contribuire al progetto:
1. Fork del repository
2. Crea branch feature (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push al branch (`git push origin feature/AmazingFeature`)
5. Apri Pull Request

## Licenza

MIT - Vedi LICENSE per dettagli
