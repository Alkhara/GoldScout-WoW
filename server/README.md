# GoldScout upload service

A small Cloudflare Worker with a D1 (SQLite) database that receives drop data
uploads from the GoldScout Companion. It only does quick checks (format, size,
terms version, upload token, rate limits) and keeps the newest export per
install. The full validation runs in the GitHub merge workflow, which reads
the uploads and opens the data pull request for review.

| Endpoint | What it does |
|---|---|
| `POST /v1/uploads` | Upload an export. The first upload from an install returns its token; later uploads need `Authorization: Bearer <token>`. |
| `GET /v1/uploads` | Admin only (`Authorization: Bearer <ADMIN_TOKEN>`): every install's newest export. `?since=<unix seconds>` limits it. |
| `GET /v1/prices` | Every WoW Forever auction house with prices: ruleset, faction, snapshot time, item count. Public. |
| `GET /v1/prices/<region>/<house>` | One house's prices: `{"itemID": [lowest unit buyout in copper, quantity listed]}`. Public. |
| `PUT /v1/admin/prices/<region>/<house>` | Admin only. `tools/ah_prices.py fetch` sends each new snapshot. |
| `PUT /v1/admin/realms/<region>` | Admin only. `tools/ah_prices.py fetch` sends the realm map from `data/ah_houses.json` (`{"realm": ruleset}`) when it changes; `GET /v1/prices` lists it as `realms`, so GoldScout Companion can pick a player's auction house. |
| `GET /health` | Returns `{"ok": true}`. |

It fits in Cloudflare's free plan.

It also starts two GitHub workflows on a schedule, because GitHub's own
schedule can skip runs for hours: `Auction prices` at :07, :22, :37 and :52,
and `Merge community data` at :17 (cron triggers in `wrangler.toml`, mapped to
workflows by `SCHEDULE` in `src/index.js`). This needs the
`GITHUB_DISPATCH_TOKEN` secret (step 6 below); without it the crons do nothing
and the workflows rely on GitHub's schedule alone.

Auction prices come from Blizzard's Game Data API (the `Auction prices`
workflow checks for new snapshots every 15 minutes). Blizzard's API terms
require naming Blizzard as the source, which every price response does, and
keeping the data at most 30 days, so older snapshots are deleted and never
served.

## Deploying

From this folder, with Node.js installed:

1. `npm install`
2. `npx wrangler login` and sign in with your Cloudflare account.
3. `npx wrangler d1 create goldscout` and copy the `database_id` it prints into
   `wrangler.toml`.
4. `npx wrangler d1 execute goldscout --remote --file schema.sql`
5. Set two secrets. Make each value long and random, for example from
   `python -c "import secrets; print(secrets.token_hex(32))"`:
   - `npx wrangler secret put ADMIN_TOKEN`: lets the GitHub merge workflow read uploads.
   - `npx wrangler secret put IP_SALT`: used to hash addresses for rate limiting.
6. Optional, to start the workflows on time: create a fine-grained GitHub
   token (GitHub → Settings → Developer settings → Fine-grained tokens) with
   access to only this repository and one permission, **Actions: Read and
   write**. Then `npx wrangler secret put GITHUB_DISPATCH_TOKEN` and paste it.
   GitHub tokens expire; replace it the same way before it does.
7. `npx wrangler deploy`. It prints the service URL, for example
   `https://goldscout-api.<your-subdomain>.workers.dev`.
8. Check it: open `<URL>/health` in a browser.
9. In GitHub (repository Settings → Secrets and variables → Actions →
   Secrets), add a repository secret `GOLDSCOUT_API_ADMIN` set to the same
   value as `ADMIN_TOKEN`. The merge workflow uses the live server's address by
   default; a repository variable `GOLDSCOUT_API_URL` overrides it.
10. Give it its own address: **Workers & Pages → goldscout-api → Settings →
   Domains & Routes → Add → Custom domain:** `api.wowgoldscout.com`. Put that
   in `companion/uploader.py` (`UPLOAD_URL`) and release a new companion.
   Leave `workers_dev` on in `wrangler.toml`: companions already installed
   keep the address they were built with.

## Admin dashboard

`/admin` shows growth, companion versions, downloads, players (as short hashed
tags), where the community data is thin, auction house freshness and workflow
health. The hourly merge workflow builds the statistics with
`tools/admin_stats.py` and sends them to `PUT /v1/admin/stats`; the page adds
live counts. It opens only behind Cloudflare Access, and the Worker also checks
Access's signature itself, so the `workers.dev` address and any misconfigured
rule stay closed. To set it up, in the Cloudflare dashboard:

1. **Workers & Pages → goldscout-api → Settings → Domains & Routes → Add →
   Custom domain:** `admin.wowgoldscout.com`.
2. **Zero Trust → Access controls → Applications → Add an application →
   Self-hosted:** name it "GoldScout admin", domain `admin.wowgoldscout.com`,
   and add a policy that allows only your email. The default login (your
   Cloudflare account) is fine; a one-time PIN by email is optional, under
   **Zero Trust → Integrations → Identity providers**. Then **Edit** the
   application and copy the **Application Audience (AUD) Tag** from
   **Additional settings**.
3. Your **team domain** is the `<team>.cloudflareaccess.com` address that
   `https://admin.wowgoldscout.com/admin` sends you to for signing in.
4. From this folder:
   - `npx wrangler secret put ACCESS_TEAM_DOMAIN` (the team domain, without https://)
   - `npx wrangler secret put ACCESS_AUD` (the AUD tag)
   - optional: `npx wrangler secret put ADMIN_EMAILS` (comma-separated; a second
     allow-list on top of the Access policy)
5. Optional, in GitHub (Settings → Secrets and variables → Actions → Variables):
   `GOLDSCOUT_MY_INSTALLS`, your own install IDs, comma-separated, to mark them.

Then open `https://admin.wowgoldscout.com/admin`. The statistics appear after
the next hourly merge run (or run "Merge community data" by hand).

## Developing locally

1. `npm install`
2. Create `.dev.vars` with `ADMIN_TOKEN=local-admin-token`, `IP_SALT=local-salt`
   and `MIN_SECONDS_BETWEEN_UPLOADS=0`. Git ignores this file. For the cron
   tests, add `GITHUB_DISPATCH_TOKEN=local-dispatch-token` and
   `GITHUB_API=http://127.0.0.1:8798`. For the admin tests, add
   `ACCESS_TEAM_DOMAIN=test.cloudflareaccess.com`, `ACCESS_AUD=test-audience` and
   `ACCESS_CERTS_URL=http://127.0.0.1:8797/certs`. To look at the dashboard
   locally, start the server with `--var ADMIN_LOCAL:1` and open
   `http://127.0.0.1:8799/admin` (that switch only works on 127.0.0.1).
3. `npx wrangler d1 execute goldscout --local --file schema.sql`
4. `npx wrangler dev --local --port 8799 --test-scheduled`
5. From the repository root:
   `GOLDSCOUT_TEST_SERVER=http://127.0.0.1:8799 GOLDSCOUT_TEST_GITHUB=8798 GOLDSCOUT_TEST_ACCESS=8797 python -m unittest tests.test_server`
