# Pentair Intellipool for Home Assistant

Unofficial Home Assistant custom integration for Pentair Intellipool pool installations.

This integration is intended for HACS distribution and uses the Intellipool cloud API to expose pool probe data as Home Assistant sensor entities.

## Installation with HACS

1. In HACS, add `https://github.com/timschps/hass-pentair` as a custom repository of type **Integration**.
2. Install **Pentair Intellipool**.
3. Restart Home Assistant.
4. Go to **Settings** → **Devices & services** → **Add integration** and search for **Pentair Intellipool**.

## Configuration

The config flow asks for:

- **Installation ID** (`install_id`)
- **API key** (`api_key`)

Both values come from the Intellipool portal (`www.intellipool.be` or `www.intellipool.eu`). The installation ID is the installation number shown in your installation list. Create the API key on the portal's **API** page.

## Entities

The integration polls the official bulk endpoint every minute by default (configurable):

```text
https://api.domotique-piscine.eu/api/install/{installId}/probes?key={key}
```

Sensors are created dynamically from the probes your installation reports, using the units supplied by the API:

- Water and air temperature, pH, ORP, conductivity
- UV, free chlorine and active chlorine, when present on the installation
- Measurement time (diagnostic)

Binary sensors expose the controller state flags: heating, filtration, lighting and aux 1.

## Limitations

The official API is read-only, so this integration cannot operate the installation (filtration, lighting, setpoints). Available probes depend on the installation.
## Disclaimer

This project is unofficial and is not affiliated with, endorsed by, or supported by Pentair or Intellipool.
