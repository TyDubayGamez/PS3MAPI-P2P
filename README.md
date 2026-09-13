# PS3 Mem Relay

- **Vercel**: backend only. One API route (`/api/ably-auth`) that hands out
  short-lived Ably tokens. Nobody visits this as a website.
- **`python/app.py`**: the actual application people run (and what gets
  packaged into an `.exe`). It's a tkinter window: enter your username, room
  code, the Vercel URL, and your own PS3's IP, and it connects you into a
  shared room with chat + a memory read/write panel.

## 1. Get an Ably API key (free)

1. Go to https://ably.com/, sign up, create an app.
2. Copy the **Root** API key.

## 2. Deploy the backend to Vercel

1. Push this folder to GitHub (make sure `package.json` ends up at the
   **root** of the repo, not nested in a subfolder) and import it on
   vercel.com, or run `vercel` from inside this folder.
2. In Vercel project settings, add an environment variable
   `ABLY_API_KEY` = the key from step 1.
3. Deploy. You'll get a URL like `https://your-app.vercel.app` - that's
   the "Backend server URL" field in the app.

## 3. Run the app

```bash
cd python
pip install -r requirements.txt
python app.py
```

Fill in:
- **Backend server URL**: your Vercel URL from step 2
- **Room code**: any string everyone in the room agrees on
- **Username**: your display name
- **Your PS3 IP / port**: your own PS3's address on your network (port
  defaults to 7887 for webMAN-MOD's PS3MAPI)

Click **Connect**. It connects to your PS3 first, then joins the room.

By default, any incoming read/write request pops up a Yes/No dialog before
touching your PS3's memory - nothing happens without you clicking Yes.
Check "Auto-approve" only with people you fully trust.

## 4. Build a standalone .exe (optional)

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
2. That publishes `mem_read_request` to the room's Ably channel.
3. Alice's app sees it's addressed to her, shows her the Yes/No dialog,
   and - if approved - calls `ps3.Process.Memory.Get(...)` against her PS3.
4. Her app publishes `mem_read_response` back to the room; Bob's app shows
   the result in his chat log.

Writes work the same way with `mem_write_request` / `mem_write_response`.

## Notes

- No real auth on the backend - anyone with your Vercel URL and a room
  code can join. Fine for a private tool among friends.
- Nothing runs against a PS3 unless that PS3's own owner is running the
  app and approves the request (or has ticked auto-approve).
