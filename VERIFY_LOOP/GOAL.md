# Goal
Deploy VoltStream to a public Fly.io URL. Fresh-clone test FIRST, then containerize, deploy, verify.

## Tasks
- T0 FRESH-CLONE TEST (critical, pre-deploy): clone the GitHub repo to a temp dir, clean venv,
  pip install -r requirements.txt, start the server. data_clean/*.csv are gitignored -> NO CSV
  fallback in a clone; app must come up in LIVE mode via the rolling store (query-endpoint
  backfill, needs ERCOT creds in env). Fix repo gaps (requirements/paths/missing files). Never
  commit data caches or secrets.
- T1 CONTAINERIZE: Dockerfile (python:3.12-slim, requirements, uvicorn 0.0.0.0:$PORT) + fly.toml.
  Cache dirs already env-driven: DART_CACHE_DIR, PRICE_CACHE_DIR, ARCHIVE_DIR -> point to /data.
  Create 1GB Fly volume, mount /data.
- T2 SECRETS + DEPLOY: flyctl secrets set ERCOT_API_USERNAME/PASSWORD/SUBSCRIPTION_KEY from
  ~/.zshenv (verify present first; if missing STOP+ask). Do NOT set ANTHROPIC_API_KEY (brief ->
  grounded template). Deploy single always-on small machine.
- T3 VERIFY PUBLIC (https): all endpoints 200 (long timeouts for first dart/risk), headless-Chrome
  render every tab, paper-book shows real ledger (not $0.00), constraints live, About renders,
  honest labels. Restart machine -> caches persisted on volume (fast 2nd boot).
- T4 README: "Live demo:" URL at top + note first DART load ~a minute. Commit, push.

## Env for the volume (already supported by the modules)
  DART_CACHE_DIR=/data/dart_cache  PRICE_CACHE_DIR=/data/dart_cache  ARCHIVE_DIR=/data
  (dart_engine reads DART_CACHE_DIR; price_store reads PRICE_CACHE_DIR + ARCHIVE_DIR;
   ercot_archiver reads ARCHIVE_DIR. journal/ ships in the image (committed ledger).)

## Verify recipe
- Local server (T0): volt-independent clean venv; LIVE mode (no ERCOT_LIVE=0); creds from ~/.zshenv;
  wait for pre-warm backfill (~seconds) then curl /api/state (must be 200 with rolling-store source).
- Public (T3): curl the fly https URL; headless Chrome per tab via #hash.
- flyctl: full path ~/.fly/bin/flyctl (not on non-interactive PATH).

## BLOCKERS found
- flyctl installed (~/.fly/bin) but NOT authed in this shell (config.yml has no token, no FLY_API_TOKEN).
  Needs resolving before T1/T2 deploy. T0 is independent.

## Guardrails: supervised, max 15 iters, one task one commit, never echo/commit secrets.
