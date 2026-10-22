# Phase 2 setup: switching on visitor video reports

Everything is built and tested; these steps connect it to your accounts. Allow about an hour.
Nothing here changes the live site until the last step.

Your project: `https://szhspqlvgiuqgbavfuhz.supabase.co`
Site: `https://railclub.github.io/rail-club-station-access/`

**Never paste a secret key into chat, the code or GitHub.** Secrets go only into the Supabase and
Google dashboards, as described below.

---

## 1. Check the region (1 min)

Supabase → your project → ⚙️ **Project Settings → General**. Region should be **South Asia (Mumbai)**.
(Anything else still works, but the privacy notice says Mumbai; tell Claude to update it.)

## 2. Create the database (5 min)

1. Supabase → **SQL Editor → New query**.
2. Paste the whole of [`supabase/migrations/20261022000000_phase2_visitor_reports.sql`](../supabase/migrations/20261022000000_phase2_visitor_reports.sql) and click **Run**. It should say "Success. No rows returned".
3. New query, add yourself as the reviewer (your admin Google account, lowercase):
   ```sql
   insert into public.admins (email) values ('your.admin.account@gmail.com');
   ```
4. Check: **Table Editor** shows `admins`, `contributors`, `facts`, `reports`, `settings`;
   **Storage** shows a private bucket `report-videos`.

## 3. Google sign-in (15 min)

**In Google Cloud** (https://console.cloud.google.com), signed in as `railclub.support@gmail.com`:

1. Create a project called **Rail Club**.
2. **Google Auth Platform → Branding** (older consoles: *OAuth consent screen*):
   - App name: `Station Access Guide (Rail Club)`
   - User support email: `railclub.support@gmail.com`
   - App home page: `https://railclub.github.io/rail-club-station-access/`
   - Privacy policy: `https://railclub.github.io/rail-club-station-access/privacy.html`
   - Authorised domain: `railclub.github.io` and `supabase.co`
   - Developer contact: your own email
3. **Audience:** External. Click **Publish app**, otherwise only test users can sign in.
   The app only asks for name and email, so Google normally doesn't require a review.
4. **Clients → Create client → Web application**, name `Rail Club web`:
   - Authorised JavaScript origins: `https://railclub.github.io`
   - Authorised redirect URIs: `https://szhspqlvgiuqgbavfuhz.supabase.co/auth/v1/callback`
5. Copy the **Client ID** and **Client secret** (keep the secret to yourself).

**In Supabase:**

6. **Authentication → Sign In / Providers → Google** → enable, paste Client ID and Client secret, Save.
7. **Authentication → URL Configuration:**
   - Site URL: `https://railclub.github.io/rail-club-station-access/`
   - Redirect URLs (add all three):
     - `https://railclub.github.io/rail-club-station-access/`
     - `https://railclub.github.io/rail-club-station-access/admin.html`
     - `http://localhost:8000/**` (for testing on your computer)

## 4. Gemini key and spending cap (10 min)

1. https://aistudio.google.com → **Get API key → Create API key** (choose the Rail Club Google Cloud project).
2. **Set up billing** for that key (AI Studio → Billing). The paid tier is needed: on the free tier
   Google may use uploaded videos to improve its products, and the privacy notice promises it doesn't.
3. **Spending cap:** Google Cloud → **Billing → Budgets & alerts → Create budget** for the Rail Club
   project, e.g. ₹500/month with email alerts at 50% and 90%. (Rail Club also stops calling Gemini
   after 300 videos a month; change `monthly_gemini_calls` in the `settings` table.)
4. Supabase → **Edge Functions → Secrets**, add:
   | Name | Value |
   |---|---|
   | `GEMINI_API_KEY` | the key from step 1 |
   | `CRON_SECRET` | any long random text, e.g. from https://www.random.org/strings/ (save it for step 6) |
   | `GEMINI_MODEL` | optional, default `gemini-2.5-flash`; set this if Google has renamed or retired it |

## 5. Deploy the server functions (10 min)

On any computer with Node.js installed, in a copy of this repository:

```bash
npx supabase login
npx supabase functions deploy submit-report review-report --project-ref szhspqlvgiuqgbavfuhz
npx supabase functions deploy cleanup --no-verify-jwt --project-ref szhspqlvgiuqgbavfuhz
```

Check: Supabase → **Edge Functions** lists `submit-report`, `review-report` and `cleanup`.

(No computer handy? Supabase → Edge Functions → **Deploy a new function → Via editor** also works:
create each function and paste its `index.ts`, plus the files from `supabase/functions/_shared/`.
For `cleanup`, turn off **Verify JWT** in its settings.)

## 6. Daily clean-up (3 min)

Supabase → **Integrations → Cron** → enable → **Create job**:
- Name: `cleanup-videos`
- Schedule: `30 21 * * *` (03:00 India time, every day)
- Type: **Supabase Edge Function** → `cleanup`, method POST
- Header: `x-cron-secret` = the `CRON_SECRET` from step 4

## 7. Switch it on and test

1. Tell Claude "Phase 2 is set up", or change `visitorReports: false` to `true` in
   [`site/config.js`](../site/config.js) and push.
2. At a station (your own first report always goes to review):
   open the station page → **Add a video of this station** → sign in → record → send.
3. Open `https://railclub.github.io/rail-club-station-access/admin.html`, sign in with the admin
   account, watch the video and **Approve**. The station page now shows "Seen by a visitor".

## If something doesn't work

| Symptom | Likely cause |
|---|---|
| Google says "redirect_uri_mismatch" | Step 3.4 redirect URI must be exactly `https://szhspqlvgiuqgbavfuhz.supabase.co/auth/v1/callback` |
| Back on the site but not signed in | Step 3.7: the page URL isn't in Supabase's Redirect URLs |
| "Only reviewers can do this" on admin.html | Step 2.3: email in `admins` must match the Google account, in lowercase |
| Every report goes to review with "Waiting for a reviewer" | `GEMINI_API_KEY` missing, Gemini error, or the monthly cap reached; see Edge Functions → submit-report → Logs |
| Function logs say `SUPABASE_SERVICE_ROLE_KEY not set` | Add it as a secret: Project Settings → API Keys → Legacy → `service_role` (secret, never share) |
| Uploads fail | Video over 12 MB, or the migration's storage policy didn't run (step 2) |

## Changing the rules later

All limits live in one row: Supabase → Table Editor → `settings` → `limits`. For example
`per_user_per_day`, `radius_m`, `trust_after_approved`, `monthly_gemini_calls`. Changes apply
immediately; no redeploy needed.
