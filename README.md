# PerfectGym for Home Assistant

A custom Home Assistant integration that signs in to PerfectGym Client Portal 2,
loads every page of recent and forthcoming bookings, and exposes them as a read-only Home
Assistant calendar entity.

The integration defaults to Christchurch City Council Rec & Sport but supports
other PerfectGym Client Portal 2 tenants by changing the portal URL during setup.

## Installation

### HACS custom repository

1. Add this repository to HACS as an **Integration** custom repository.
2. Install **PerfectGym**.
3. Restart Home Assistant.

### Manual

Copy `custom_components/perfectgym` into the `custom_components` directory in
your Home Assistant configuration directory, then restart Home Assistant.

## Setup

1. In Home Assistant, go to **Settings → Devices & services**.
2. Select **Add integration** and search for **PerfectGym**.
3. Keep the default Client Portal URL for Rec & Sport, then enter the email/login
   and password you use at the PerfectGym portal.

The calendar refreshes daily. JWTs are kept only in memory and the
integration signs in again automatically when a token expires. Home Assistant's
config entry stores the member credentials so it can sign in after restarts.

Each calendar event includes its class name, UTC-correct start/end times, club and
zone, participants, trainer, standby status, and booking ID when supplied by the
portal. The integration is read-only and cannot create, alter, or cancel bookings.

## Notes

- This uses the web API used by Client Portal 2; it is not an officially supported
  PerfectGym API integration and may need updates if the portal changes.
- The initial calendar API is paginated. Additional recent and future pages are
  fetched, so today's bookings and later events are both included.
- Do not paste a bearer token into configuration. Tokens expire and are obtained
  automatically from the login endpoint.

## Troubleshooting

`PerfectGym service temporarily unavailable (HTTP 503)` means the PerfectGym
gateway was unavailable; it does not mean the username or password was rejected.
The integration retries brief 429/502/503/504 failures three times, after which
Home Assistant schedules another setup or coordinator refresh automatically.
