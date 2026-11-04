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
