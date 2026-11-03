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

7. `db/`: the app's own limited database user (`init-app-user.sh`, runs once) and its rights (`grants.sql`).

8. `nginx/security-headers.conf`: security headers and the Content-Security-Policy, used by every page.


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
   openssl rand -hex 24    # use this for POSTGRES_PASSWORD (and inside MIGRATION_DATABASE_URL)
   openssl rand -hex 24    # a DIFFERENT one for APP_DB_PASSWORD (and inside DATABASE_URL)
   nano .env
   ```

   Two database users: `kjs` owns the tables (migrations, backups) and `kjs_app` is what the app uses.
   `kjs_app` may only read and write rows, and can never change the audit log.

   The API refuses to start if something is still unsafe (default secret, `http://` address,
   localhost in ALLOWED_ORIGINS, example database password). The log says exactly which one.


5. First deploy

   ```bash
   ./deploy.sh
   docker compose -f docker-compose.prod.yml run --rm backend python -m app.seed   # categories + first admin
   ```

   Check it on the server: `curl http://127.0.0.1:8080/api/health/ready` should say `"ready"`.

   Then log in, change the admin password (Profile), and delete the `FIRST_ADMIN_*` lines from `.env`.


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
   vii.  Leave Cloudflare's "Rocket Loader" and other script-injecting features OFF: our
         Content-Security-Policy would block them (and they aren't needed).


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

   It backs up, migrates, restarts, and waits for the health check. It keeps the last 3 image versions
   and writes the live version into `.env` (`TAG=<commit>`), so every later command uses that version.


2. Change a setting (SLA minutes, batch size, feature on/off)

   Edit `../config/*.ini` and save. It applies within a few seconds. No restart.


3. Change a secret in `.env`

   ```bash
   docker compose -f docker-compose.prod.yml up -d --no-build    # recreates containers with the new values
   ```

   Always use `--no-build` with a plain `up`: it runs the version recorded in `TAG`, never untested code.


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

2. Put the previous one in `.env` and start it:

   ```bash
   sed -i 's/^TAG=.*/TAG=<previous-commit>/' .env
   docker compose -f docker-compose.prod.yml up -d --no-build backend frontend
   docker compose -f docker-compose.prod.yml exec -T nginx nginx -s reload   # find the new containers now
   ```

   Because the version is in `.env`, it stays rolled back after any restart.

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

   It asks you to type RESTORE, then:

   i.    reads both backups in full (a bad one stops here: nothing changed, the app never stopped),
   ii.   stops the app,
   iii.  backs up the CURRENT state (so a wrong restore can be undone, with nothing missing),
   iv.   unpacks the new files aside (if you gave a files backup), so the disk needs room for both the
         old and the new files during the restore,
   v.    replaces the database in one transaction (if this fails, the database stays as it was),
   vi.   swaps in the new files,
   vii.  updates the tables to the current code version and re-applies the app user's rights,
   viii. starts the app again (also when something failed) and checks that the API answers. If the
         script was stopped during step v, the app stays stopped, because the restore may still finish.

   If it fails after step v, or the app doesn't work afterwards, it prints the exact `./restore.sh` command
   that puts the safety backup back. That command is also added to `/srv/kjs/backups/restore-undo.txt`
   (in case the SSH session drops), one entry per restore, newest at the end. Safety backups are named
   `...-before-restore`. When the restore ends, its entry says so: running that command later also
   throws away everything saved since then. If nothing was changed, the entry says there is nothing to undo.
   If an earlier restore is still running inside the database, it refuses to start: wait, then run it again.
   Changes to `restore.sh` or `backup.sh`: run `./test-restore.sh` on your own machine, never on the server.


3. Restore drill (once a month, and before go-live)

   i.    Copy the newest backup to another machine with Docker.
   ii.   Clone the repo, make a `.env` for testing, `docker compose -f docker-compose.prod.yml up -d db backend`.
   iii.  `./restore.sh <files> --yes`, then log in and check that recent data is there.
   iv.   Write the date and the result in `docs/track.md`.


4. Off-site copy

   A backup on the same disk is lost with the disk. Copy `/srv/kjs/backups` to another place every night,
   for example a Cloudflare R2 bucket with `rclone` (a new tool: ask before installing).
   Encrypt it before it leaves the server (for example `age` or `gpg`): it holds customer data.
   Decide this with the KJS IT contact.

5. Backups are readable only by the user who runs `backup.sh` (folder 700, files 600).
   Run the cron job as that same user, never as a shared account.



## 6. Using Neon (or another hosted Postgres) instead of the db container

1. Put the hosted address in `.env` as `DATABASE_URL` (and `MIGRATION_DATABASE_URL` for the direct one).
   Create a limited app user there too, with the rights in `db/grants.sql`.

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
