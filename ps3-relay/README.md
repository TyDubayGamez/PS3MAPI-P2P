# PS3 Mem Relay

A room-based relay: a Next.js app on Vercel hosts the chat/room UI and hands
out realtime tokens; a Python agent (using your `ps3mapi.py`) runs on each
person's own PC, joins the same room, and is the only thing that actually
talks to a PS3.

## 1. Get an Ably API key (free)

1. Go to https://ably.com/ and sign up.
2. Create an app (any name).
3. Copy the **Root** API key (looks like `abc123.def456:ghijkl...`).

## 2. Deploy to Vercel

1. Push this folder to a GitHub repo (or `vercel` CLI can deploy straight
   from a local folder — `npm i -g vercel` then `vercel` from inside this
   directory).
2. In the Vercel project settings, add an Environment Variable:
   - `ABLY_API_KEY` = the key from step 1.
3. Deploy. You'll get a URL like `https://your-app.vercel.app`.

## 3. Use the web room

Open the deployed URL, enter a username, and either create a room (get a
code) or join one your friend gave you. This gives you chat + a "memory
panel" for requesting reads/writes — but nothing actually happens on a PS3
until your agent (next step) is running.

## 4. Run your local agent

Each person who wants their own PS3 reachable runs this on their own PC,
on the same network as their PS3:

```bash
cd python
pip install -r requirements.txt
python relay_client.py \
    --server https://your-app.vercel.app \
    --room ABCDE \
    --username alice \
    --ps3-ip 192.168.1.50
```

While it's running, it listens for read/write requests addressed to
`alice` in room `ABCDE`. By default it prints a `y/N` prompt in the
terminal for every incoming request before touching memory — so nothing
happens on your console without you approving it in the moment. Pass
`--auto-approve` to skip that if you fully trust everyone in the room.

## How a request flows

1. Bob, in the web room, fills in target=`alice`, pid, address, length and
   clicks **Read**.
2. That publishes a `mem_read_request` event to the room's Ably channel.
3. Alice's running `relay_client.py` sees it's addressed to her, prompts
   her in the terminal, and — if approved — calls
   `ps3.Process.Memory.Get(...)` from your `ps3mapi.py` against her PS3.
4. It publishes the result back as `mem_read_response`, which both the web
   room and Bob's own agent (if running) can see.

Writes work the same way with `mem_write_request` / `mem_write_response`.

## Notes / next steps

- This has no real auth — anyone with the room code and your Vercel URL
  can join. Fine for a private tool among friends, not fine to expose
  publicly.
- The web memory panel currently sends raw hex; you could add presets for
  specific games/addresses later.
- If you want the *browser itself* to show live memory values (e.g. a
  polling readout), that's a small addition — have the agent respond to a
  request on an interval and update state in the room page.
