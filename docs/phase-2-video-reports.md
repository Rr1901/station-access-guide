# Phase 2: visitor video reports

Status: **built and tested, not switched on yet.** Backend: Supabase (Auth, Postgres, Storage,
Edge Functions) with Gemini. To switch it on, follow [phase-2-setup.md](phase-2-setup.md).

Where things are:
- Gates and decision rules: `supabase/functions/_shared/rules.ts` (tests in `supabase/functions/tests/`)
- Gemini prompt, schema and answer checks: `supabase/functions/_shared/gemini.ts`
- Server functions: `submit-report`, `review-report` (admins), `cleanup` (daily)
- Database, security rules and the private video bucket: `supabase/migrations/`
- Station page section and recording flow: `site/report.js`; review queue: `site/admin.html`;
  privacy notice: `site/privacy.html`; on/off switch: `site/config.js`

Gates, in order (free ones first, Gemini last): signed in → not blocked → daily limits (3 per person,
20 per station) → GPS within the station area (400 m, up to 700 m for big stations) and accurate to
100 m → recorded live, 15–60 s, uploaded within 10 minutes → real video file under 12 MB → not a
duplicate → still needed (not official "yes", not confirmed by 2 visitors in 90 days) → monthly
Gemini budget → Gemini → decision rules. The station board is a bonus, not a requirement; Gemini
checks the scene is inside a railway station.

Most divisions haven't published station-wise accessibility data. Phase 2 lets
visitors fill the gaps by recording a short video at a station; Gemini checks it
and pulls out what it shows.

## Flow

1. **Visitor opens a station page and taps "Add a video".**
2. **Location check.** The browser asks for their location. It must be within
   about 300 m of the station. Coordinates come from the CC0 datameet station
   list (`stations.json`, ~9,000 stations with coordinates), already used for
   station codes.
3. **Record, don't upload.** The page records a 20–60 second clip straight from
   the camera (`getUserMedia` + `MediaRecorder`). No gallery uploads: recording
   live means the video is from today, at that place.
4. **Gemini checks the video:**
   - reads the station name boards (on every platform, in three languages) and
     confirms they match the station: the strongest proof of place;
   - lists what it sees, with a timestamp for each: "lift, PF 1, 0:12",
     "ramp at entrance, 0:31";
   - flags anything wrong: no station board visible, a screen being filmed, or a
     mismatch with the location.
5. **Publish.** The facts go on the station page as "Seen by a visitor on
   20 Oct 2026".

## Rules for the data

- **Videos only add "seen" facts.** A video can't prove something is missing;
  the camera may just not have pointed at it. Nothing from a video ever sets a
  feature to "Not available".
- New division method `"video"`, alongside `parsed-*` and `secondary`. Each fact
  keeps its recording date and timestamp; newer official data wins over older
  video reports.
- Shown with its own label ("Seen by a visitor on …") and the same
  "call 139 before you travel" caveat as secondary sources.

## What it needs

- **A small backend.** The site is static (GitHub Pages). Uploads, the Gemini
  API key and the review queue need a server: Firebase, Supabase or Cloudflare
  Workers. The Gemini key must never be in the page.
- **Review before publishing, at first.** Gemini sorts videos into "looks good"
  and "rejected"; the maintainer approves with one tap. Auto-publish later, only
  when location, station board and recording time all check out.
- **Privacy (DPDP Act 2023).** Videos show other passengers. Keep only the facts
  Gemini extracts; show the video only to the reviewer; delete it after review.
- **Limits.** Each video costs Gemini credits: rate-limit per person per day.

## Gemini output shape

```json
{
  "station_board_seen": true,
  "station_board_text": "RAJKOT JN / राजकोट जं. / રાજકોટ જં.",
  "matches_station": true,
  "problems": [],
  "features": [
    {"key": "lift", "where": "PF 1", "at": "0:12", "confidence": "high"},
    {"key": "ramp_entry", "where": "main entrance", "at": "0:31", "confidence": "medium"}
  ]
}
```

`key` uses the feature keys in `scraper/features.py`.

## Open decisions

- Backend: Firebase, Supabase or Cloudflare.
- When to switch from reviewed to auto-published.
