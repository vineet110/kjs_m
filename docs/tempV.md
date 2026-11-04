# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).


## Image serving plan (4 Nov, plan only, no code yet)

How it works today:

1. Fixed site images (logo, banners, the 58 product cut-outs) sit in `frontend/public/images/`.
   `next/image` resizes them and turns them into WebP. This part is fine.
2. Uploaded files go through `backend/app/core/storage.py` (local folder now, Cloudflare R2 later).
   The database keeps only the key. This matches decision D16 and stays.
3. Public product photos are served by `/api/v1/public/files/{id}`, only while the product is live.

Two gaps to fix before staff start uploading real product photos.


### Gap 1. Uploaded photos are sent at full size

1. The problem
   i.    The product page shows uploaded photos with `unoptimized` (`products/[slug]/page.tsx:61`).
   ii.   A 10 MB phone photo reaches the visitor as 10 MB. Slow on mobile data, bad for SEO.
   iii.  Phone photos also carry EXIF data, which can include the GPS location of where they were taken.

2. Plan (recommended): shrink the photo once, when it is uploaded
   i.    Only for image files (png, jpg, jpeg, webp). PDFs and Excel files are not touched.
   ii.   Open the image. If it can't be opened, reject it ("not a real image"). This also fixes the
         "checked by file name only" problem for images.
   iii.  Resize so the longest side is at most 1600 px. Smaller images are left at their own size.
   iv.   Save as WebP (quality about 80). Drop the EXIF data (GPS, camera details).
   v.    Store only the small version. `content_type` becomes `image/webp`, `size` is the new size.
   vi.   Protect against "decompression bombs" (a tiny file that opens into a huge image): keep
         Pillow's pixel limit on, and reject anything above it.

3. Needs a new dependency: **Pillow** (the standard Python image library). Ask before adding (CLAUDE.md).

4. Why not let Next.js resize them instead (remove `unoptimized`)?
   i.    It would also work, but the frontend server then does the resizing on every first request,
         and the big original still sits in storage and backups.
   ii.   It would also need testing with R2's redirect, which I haven't done.
   iii.  Shrinking at upload fixes size, privacy and the file check in one place.

5. Files it touches: `backend/app/services/file_service.py`, `backend/requirements.txt`,
   new tests in `backend/tests/test_files.py`. Not in Nishita's claimed list.


### Gap 2. With R2, public photo links expire after 5 minutes

1. The problem
   i.    With `STORAGE_DRIVER=r2`, `/api/v1/public/files/{id}` answers with a redirect to a signed R2
         link that works for 5 minutes. A new link is made every time.
   ii.   So the browser and Cloudflare can't cache the photo. Every view hits FastAPI and the database.
   iii.  The signed link also says "attachment" (download), which is meant for staff files.
   iv.   Today (local storage) this doesn't happen: the API streams the file with a 1-hour cache header.

2. Plan (recommended, small): stream public photos instead of redirecting
   i.    For public website files only, the API reads the photo from R2 and sends it itself,
         with the same `public, max-age=3600` header used today. Staff files keep the 5-minute link.
   ii.   Works because of Gap 1: photos are now small (a few hundred KB), so streaming them is cheap.
   iii.  Keeps our rule: when a product is hidden, its photos stop being public (within the 1-hour cache).
   iv.   Add a Cloudflare Cache Rule for `/api/v1/public/files/*`. Cloudflare doesn't cache addresses
         without a file extension (.jpg, .png) unless told to. Then most views never reach our server.

3. Bigger option for later (only if traffic grows): a separate public R2 bucket on a custom domain
   (for example `media.kjsindia.com`). Fastest, but a hidden product's photos stay reachable to anyone
   who has the link, so we'd lose the rule in 2.iii.

4. Files it touches: `backend/app/services/file_service.py`, `backend/app/api/v1/endpoints/files.py`,
   maybe `backend/app/core/storage.py`. Not in Nishita's claimed list. No new dependency.


### Order

1. Gap 1 first (it makes Gap 2 cheap). One small PR each.
2. Gap 2 only matters once R2 keys arrive. Until then local storage is fine.


### Assumptions (add to backlog section 3 when folding)

1. 1600 px longest side is enough for the product page. Change if KJS wants zoom on photos.
2. We don't need to keep the original full-size photo. If KJS wants originals, keep both (more storage).
3. A hidden product's photos may still show for up to 1 hour from cache. Assumed OK.


### New terms (add to kb.md when folding)

1. EXIF: extra data inside a photo (camera, date, sometimes GPS location).
2. WebP: an image format, usually much smaller than JPG at the same quality.
3. Decompression bomb: a small file that opens into a giant image to use up the server's memory.
4. Signed (presigned) URL: a link to a private file that works only for a short time.
5. Cache Rule: a Cloudflare setting that tells it which addresses it may keep copies of.


## Other gaps found (4 Nov, list only, no code yet)

Found while checking the image setup. Items that already have a backlog entry are marked "already logged".

1. No error pages
   i.    No `not-found.tsx`, `error.tsx` or `global-error.tsx` in `frontend/src/app/`.
   ii.   A bad product link or a crash shows Next.js's plain default page, with no KJS look and no way back.
   iii.  Small fix, no dependency. Do first.

2. Nobody hears about crashes or downtime
   i.    Errors only go to the logs. Nothing alerts us.
   ii.   No outside check of `/api/health`, so a site that is down goes unnoticed.
   iii.  Fix: a free uptime checker that calls `/api/health/ready`. Error tracking (like Sentry) would be a
         new service: ask first.

3. Backups stay on the same server (already logged: R11)
   i.    If the disk dies, the backups die with it. Not encrypted, no alert when a backup fails.
   ii.   Needs KJS IT (where to keep the off-site copy).

4. Staff pages can stay on "Loading…" forever (already logged: R40)

5. Uploads checked by file name only (already logged: R9)
   i.    The image plan above fixes this for photos. PDFs and Excel files still need a check of the
         first bytes ("magic bytes").

6. Light spam protection (already logged: A31)
   i.    Honeypot + per-IP limit only. Turnstile still to do (needs a Cloudflare account).

7. Big videos in git
   i.    About 13 MB of MP4s in `frontend/public/images/kjs/video/` (`banner-video.mp4` alone is 6.8 MB).
   ii.   Fix: compress them, or move them to R2 once we have it.

8. Waiting on KJS, not on code (already logged)
   i.    SMTP details (I10), domain and DNS (B6), company server (B3), R2 keys (A54).
   ii.   Must fix before go-live: sales phone number (A76 / I14), partner offer (A47 / I12).

Suggested order: 1 and 2 first (small, and we hear about problems before visitors do), then the image plan.


### New terms (add to kb.md when folding)

1. Uptime checker: an outside service that opens our site every few minutes and alerts us if it fails.
2. Error tracking: a service that collects every crash with details, so we can fix it.
3. Magic bytes: the first few bytes of a file that show its real type, whatever its name says.
4. Turnstile: Cloudflare's free check that a visitor is a person, not a bot.
