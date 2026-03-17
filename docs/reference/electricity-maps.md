# Electricity Maps API

Real-time carbon intensity data for power grids. We use this to make inference adapt to grid conditions.

## Signup

Free tier at [app.electricitymaps.com/auth/signup](https://app.electricitymaps.com/auth/signup). Gives you an API token.

**API key location:** `~/.config/electricity_maps/api_key`

**Free tier caveat:** Sandbox data only — returns real structure but with ±30% randomization on values. Fine for prototyping and validating integration. Need paid tier for accurate data.

## API

### Current carbon intensity

```
GET https://api.electricitymaps.com/v3/carbon-intensity/latest?zone=US-CAL-CISO
Header: auth-token: <token>
```

Response:
```json
{
  "zone": "US-CAL-CISO",
  "carbonIntensity": 123,
  "datetime": "2026-03-17T12:00:00Z",
  "updatedAt": "...",
  "isEstimated": true,
  "estimationMethod": "...",
  "emissionFactorType": "lifecycle"
}
```

`carbonIntensity` is gCO2eq/kWh.

### Other useful endpoints

- `/v3/carbon-intensity/history?zone=US-CAL-CISO` — last 24h
- `/v3/carbon-intensity/forecast?zone=US-CAL-CISO` — forward-looking

Optional params: `emissionFactorType` (lifecycle|direct), `temporalGranularity` (5min|15min|hourly).

## California (CAISO) typical ranges

Follows the duck curve — solar drives midday low, gas ramp drives evening peak.

| Time of day | gCO2/kWh | Grid state |
|-|-|-|
| Midday (11am–3pm) | 80–150 | Solar peak, clean |
| Afternoon (3–6pm) | 200–300 | Solar declining |
| Evening peak (6–9pm) | 350–450 | Gas ramp, dirtiest |
| Overnight (9pm–6am) | 250–350 | Moderate |

## Mock fallback

If no internet at the hackathon, simulate with a sinusoid: ~100 at 1pm, ~400 at 8pm, ~280 overnight.

## Alternatives

- **WattTime** — covers CAISO, free tier for basic signal index, requires signup + username/password auth
- **co2signal.com** — dead (522 error), was the old free Electricity Maps proxy
- **UK Carbon Intensity API** — free, no auth, but UK only
