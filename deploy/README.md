# Deploy guide (company server)

How to put the platform on the KJS server, update it, roll back, and back it up.

Every command runs on the server (Linux), from the `deploy/` folder, unless it says otherwise.



## 1. What is in this folder

1. `docker-compose.prod.yml`: the whole system: database, API, website, nginx, Cloudflare Tunnel.

2. `.env.production.example`: every setting production needs. Copy it to `.env` and fill it in.

3. `nginx/default.conf`: nginx settings (sends `/api` to FastAPI, everything else to Next.js).

4. `deploy.sh`: update to the latest code (backup first, then migrate, then restart).

5. `backup.sh`: backup of the database and uploaded files.

6. `restore.sh`: put a backup back.


How a visitor reaches us:

   Internet -> Cloudflare (HTTPS) -> cloudflared (tunnel) -> nginx -> website / API -> database

No port on the server is open to the internet. cloudflared connects out to Cloudflare.



## 2. First-time setup

1. Install on the server

   i.    Docker Engine + the compose plugin: https://docs.docker.com/engine/install/
   ii.   git
   iii.  Check: `docker compose version`


2. Get the code

   ```bash
   sudo mkdir -p /srv/kjs && sudo chown $USER /srv/kjs
   git clone https://github.com/vineet110/kjs_m.git /srv/kjs/app
   cd /srv/kjs/app/deploy
   ```


3. Website videos (they are not in git, too big)

   ```bash
   python3 ../scripts/fetch_kjs_assets.py ../frontend/public/images/kjs /tmp/site-text.md
   ```


4. Settings

   ```bash
   cp .env.production.example .env
   chmod 600 .env          # only you can read it
   openssl rand -hex 32    # use this for SECRET_KEY
   openssl rand -hex 24    # use this for POSTGRES_PASSWORD (and inside DATABASE_URL)
   nano .env
   ```

   The API refuses to start if something is still unsafe (default secret, `http://` address,
   localhost in ALLOWED_ORIGINS, example database password). The log says exactly which one.


5. First deploy

   ```bash
   ./deploy.sh
   docker compose -f docker-compose.prod.yml run --rm backend python -m app.seed   # categories + first admin
   ```

   Check it on the server: `curl http://127.0.0.1:8080/api/health/ready` should say `"ready"`.


6. Cloudflare Tunnel (makes the site reachable from the internet, with HTTPS)

   i.    Cloudflare dashboard -> Zero Trust -> Networks -> Tunnels -> Create a tunnel -> "Cloudflared".
   ii.   Name it `kjs`. Copy the token (the long text after `--token`).
   iii.  Put it in `.env` as `CLOUDFLARE_TUNNEL_TOKEN=...`
   iv.   In the tunnel: Public Hostname -> add `www.kjsindia.com` (or the chosen subdomain),
         Service: `HTTP`, URL: `nginx:80`.
   v.    Start it:

   ```bash
   docker compose -f docker-compose.prod.yml --profile tunnel up -d
   ```

   vi.   In Cloudflare -> SSL/TLS: mode "Full", turn on "Always use HTTPS" and HSTS.


7. Nightly backups (cron)

   ```bash
   crontab -e
   # add this line: every night at 02:30
   30 2 * * * /srv/kjs/app/deploy/backup.sh >> /srv/kjs/backups/backup.log 2>&1
   ```



## 3. Everyday tasks

1. Update to the latest code on `main`

   ```bash
   ./deploy.sh
   ```

   It backs up, migrates, restarts, and waits for the health check. It keeps the last 3 image versions.


2. Change a setting (SLA minutes, batch size, feature on/off)

   Edit `../config/*.ini` and save. It applies within a few seconds. No restart.


3. Change a secret in `.env`

   ```bash
   docker compose -f docker-compose.prod.yml up -d    # recreates containers with the new values
   ```


4. Look at logs

   ```bash
   docker compose -f docker-compose.prod.yml logs -f --tail 100 backend
   docker compose -f docker-compose.prod.yml logs backend | grep <request_id>   # one request
   ```


5. See what is running

   ```bash
   docker compose -f docker-compose.prod.yml ps
   ```



## 4. Roll back (a new version is broken)

1. See which versions exist: `docker image ls kjs-api`  (tags are git commits, newest first)

2. Start the previous one:

   ```bash
   TAG=<previous-commit> docker compose -f docker-compose.prod.yml up -d --no-build backend frontend
   ```

3. If the broken version changed the database (a new migration), also restore the backup that
   `deploy.sh` made just before it (section 5).

4. Fix the bug on a branch, merge to `main`, run `./deploy.sh` again.



## 5. Backups and restore

1. Where: `/srv/kjs/backups/` (change with `BACKUP_DIR=...`). Kept 14 days (`KEEP_DAYS=...`).

   i.    `db-<date>.dump`: the whole database.
   ii.   `files-<date>.tgz`: uploaded files (when `STORAGE_DRIVER=local`).


2. Restore

   ```bash
   ./restore.sh /srv/kjs/backups/db-20261210-023000.dump /srv/kjs/backups/files-20261210-023000.tgz
   ```

   It asks you to type RESTORE, stops the app, replaces the database (and files), and starts the app.


3. Restore drill (once a month, and before go-live)

   i.    Copy the newest backup to another machine with Docker.
   ii.   Clone the repo, make a `.env` for testing, `docker compose -f docker-compose.prod.yml up -d db backend`.
   iii.  `./restore.sh <files> --yes`, then log in and check that recent data is there.
   iv.   Write the date and the result in `docs/track.md`.


4. Off-site copy

   A backup on the same disk is lost with the disk. Copy `/srv/kjs/backups` to another place every night,
   for example a Cloudflare R2 bucket with `rclone` (a new tool: ask before installing).
   Decide this with the KJS IT contact.



## 6. Using Neon (or another hosted Postgres) instead of the db container

1. Put the hosted address in `.env` as `DATABASE_URL` (and `MIGRATION_DATABASE_URL` for the direct one).

2. Remove the `db` service from the compose file, and the `depends_on: db` under backend.

3. `backup.sh` dumps through the `db` container, so change step 1 to:

   ```bash
   docker run --rm postgres:17-alpine pg_dump "<direct postgres:// address>" -Fc > "$db_file.tmp"
   ```



## 7. If something goes wrong

1. API won't start, log says `config.unsafe_for_production`: fix the value it names in `.env`.

2. Website shows "Something went wrong" everywhere: `logs backend`. Usually the database.

3. Everyone gets "too many requests": nginx is not passing the visitor IP. Check
   `proxy_set_header X-Forwarded-For` is still in `nginx/default.conf` (backlog A45).

4. Upload fails with 413: the file is bigger than `client_max_body_size` in `nginx/default.conf`.

5. Disk full: `docker system df`, then `docker image prune` and check `/srv/kjs/backups`.
