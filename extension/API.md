# KJS Work Tracker extension: API

What the browser extension sends to the portal and what comes back. The backend side is
`backend/app/api/v1/endpoints/ext.py`; the rules are in `backend/app/services/extension_service.py`.

Base address: `https://<portal>/api/v1/ext`. All bodies are JSON unless noted.

Errors always look like `{code, message, details, request_id}` (same as the rest of the API).



---------------------------------------------------------------------------------------------------

## 1. Connecting (once per computer)

1. The employee opens My activity in the portal and clicks "Connect extension". The portal shows a code
   like `KJS-7K3Q-9XD2`. It works once, for `pair_code_minutes` (10).

2. The employee pastes it into the extension popup. The extension sends:

   `POST /connect`  body `{"code": "KJS-7K3Q-9XD2", "name": "Chrome on Windows"}`

   i.    200 `{"key": "<device key>", "device_id": 12, "user_name": "Ravi Kumar"}`
   ii.   400 `bad_code`: wrong, used or expired code.
   iii.  429: too many wrong codes from this network (20 per hour).

3. Keep `key` in `chrome.storage.local`. It is shown only this once; the server keeps only a hash.

4. Every other call sends the header `Authorization: Bearer <key>`.

   i.    401 `bad_device`: the key is unknown or was switched off (by the employee or an admin). Delete the
         key and show "Not connected. Connect again from My activity."
   ii.   404 `module_off`: monitoring is switched off. Do nothing; ask again later.



---------------------------------------------------------------------------------------------------

## 2. Status (ask before recording, and every `send_minutes`)

`GET /status`

```
{
  "user_name": "Ravi Kumar",
  "checked_in": true,
  "on_break": false,
  "server_time": "2026-11-15T10:02:11+05:30",
  "config": {
    "send_minutes": 5,
    "idle_warn_minutes": 15,
    "never_record": ["hdfcbank.com", "icicibank.com"],
    "screenshot_minutes": 15,
    "image_quality": 60,
    "max_screenshot_kb": 600
  }
}
```

1. Record only while `checked_in` is true and `on_break` is false.

2. Never record a domain in `never_record` (subdomains included), or any incognito window.

3. Use the config numbers from here, never hard-coded ones: admins change them in `config/monitoring.ini`.



---------------------------------------------------------------------------------------------------

## 3. Site visits (every `send_minutes`)

`POST /sites`

```
{
  "visits": [
    {
      "id": "3f2a9c1e-0b7d-4a51-9c3e-7f1a2b3c4d5e",
      "url": "https://www.indiamart.com/search?q=twill",
      "title": "Twill fabric suppliers, Surat",
      "started_at": "2026-11-15T10:00:05+05:30",
      "ended_at": "2026-11-15T10:04:40+05:30"
    }
  ]
}
```

1. One visit = the time one tab was the active tab in a focused window, on one address.

2. `id`: a random id the extension makes for each visit (1 to 40 characters). Keep a visit with the same
   id until the server has answered 200: sending the same visit again is safe, it is saved once.

3. Times with a time zone (ISO 8601). At most 500 visits per call.

4. Answer: `{"saved": 1, "skipped": 0}`.

   i.    `skipped`: not an http(s) address, a `never_record` site, or the person wasn't checked in at
         any moment of it. Not an error: drop it.

5. What the server does (the extension doesn't need to): cuts each visit to checked-in time, drops the
   `?query` and `#fragment` (unless `store_query = true`), adds the time to that site's hour.

6. Offline: keep visits in `chrome.storage.local` and send them when back online (oldest first, 500 at a
   time). Drop visits older than 2 days.



---------------------------------------------------------------------------------------------------

## 4. Idle

Use `chrome.idle.setDetectionInterval(idle_warn_minutes * 60)`. When the state becomes `idle` or `locked`:

`POST /idle`  body `{"state": "started", "at": "<now minus the detection interval>"}`

When it becomes `active` again:

`POST /idle`  body `{"state": "ended", "at": "<now>"}`

1. Answer `{"ok": true}`. Ignored by the server when checked out or on a break.

2. The portal shows the warning (with "On a call", "In a meeting", "Other"). The extension also shows a
   Windows notification: "No activity for 15 minutes. This will be reported to admin soon."



---------------------------------------------------------------------------------------------------

## 5. Screenshots and screen sharing (Phase D: the extension takes over from the portal)

1. `POST /share`  body `{"state": "started" | "stopped" | "refused"}`

2. `POST /screenshot`  multipart form, field `file`: a JPEG, at most `max_screenshot_kb`.

   i.    200 `{"id": 41, "taken_at": "..."}`
   ii.   409 `not_checked_in` or `on_break`, 429 `too_soon`, 413 `too_big`, 400 `bad_image`: don't retry.
   iii.  503 `storage_down`: try again next time.

3. Capture with `chrome.desktopCapture.chooseDesktopMedia(["screen"])`, keep the stream in an offscreen
   document (so a portal reload doesn't stop it), take one frame every `screenshot_minutes`.

4. When sharing stops (Chrome closed, "Stop sharing" clicked): send `stopped`, and show a notification
   "Screen sharing stopped. Click to resume." A click opens the picker again.
