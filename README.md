# PS3 Mem Relay

- **Vercel**: backend only. Two API routes (`/api/send`, `/api/poll`) backed
  by Vercel KV - no third-party realtime service needed. Nobody visits this
  as a website.
- **`python/app.py`**: the actual application people run (and what gets
  packaged into an `.exe`). It's a tkinter window: enter your username, room
  code, the Vercel URL, and your own PS3's IP, and it connects you into a
  shared room with chat + a memory read/write panel.

## How it works

There's no realtime push here - the app polls `/api/poll` about once a
second for anything new, and posts to `/api/send` when you do something.
Vercel KV just stores each room's messages as a list (trimmed to the last
500). This means no Ably account, no separate signup - everything lives in
your Vercel project. The trade-off is a ~1 second delay instead of instant
delivery, which is unnoticeable for chat + occasional memory requests.

## 1. Add Vercel KV to your project

1. Push this folder to GitHub (make sure `package.json` ends up at the
   **root** of the repo, not nested in a subfolder) and import it on
   vercel.com, or run `vercel` from inside this folder, same as before.
2. In your Vercel project, go to the **Storage** tab -> **Create Database**
   -> **KV**. Follow the prompts to create it and connect it to this
   project. Vercel automatically injects the right environment variables
   (`KV_REST_API_URL`, `KV_REST_API_TOKEN`, etc.) - you don't set anything
   manually like you did with the old Ably key.
3. Redeploy (Deployments tab -> latest deployment -> Redeploy) so the build
   picks up the new environment variables.
4. Your app's URL is unchanged - still something like
   `https://your-app.vercel.app`. That's the "Backend server URL" field in
   the app.

## 2. Run the app

```bash
cd python
pip install -r requirements.txt
python app.py
```

Fill in:
- **Backend server URL**: your Vercel URL
- **Room code**: any string everyone in the room agrees on
- **Username**: your display name
- **Your PS3 IP / port**: your own PS3's address on your network (port
  defaults to 7887 for webMAN-MOD's PS3MAPI)

Click **Connect**. It connects to your PS3 first, then joins the room.

By default, any incoming read/write request pops up a Yes/No dialog before
touching your PS3's memory - nothing happens without you clicking Yes.
Check "Auto-approve" only with people you fully trust.

## 3. Build a standalone .exe (optional)

```bash
cd python
pip install pyinstaller
pyinstaller --onefile --noconsole app.py
```

The `.exe` will show up in `python/dist/app.exe`. `ps3mapi.py` needs to sit
next to `app.py` when you build it (PyInstaller bundles local imports
automatically).

## How a request flows

1. Bob fills in target=`alice`, pid, address, length in his app and clicks
   **Read**.
2. That posts a `mem_read_request` event to `/api/send`, which appends it
   to the room's list in Vercel KV.
3. Alice's app polls `/api/poll` within about a second, sees the request is
   addressed to her, shows her the Yes/No dialog, and - if approved - calls
   `ps3.Process.Memory.Get(...)` against her PS3.
4. Her app posts a `mem_read_response` event back; Bob's app picks it up on
   its next poll and shows the result in his chat log.

Writes work the same way with `mem_write_request` / `mem_write_response`.

## Notes

- No real auth on the backend - anyone with your Vercel URL and a room
  code can join. Fine for a private tool among friends.
- Nothing runs against a PS3 unless that PS3's own owner is running the
  app and approves the request (or has ticked auto-approve).
- Room queues are capped at the last 500 messages each, so old chat/request
  history quietly falls off - fine for a live session, not meant as a log.
