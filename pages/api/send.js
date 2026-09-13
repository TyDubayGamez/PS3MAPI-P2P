import { kv } from "@vercel/kv";

// Appends one event to a room's message queue. Body: { room, event, data }
export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "POST only" });
    return;
  }

  const { room, event, data } = req.body || {};
  if (!room || !event) {
    res.status(400).json({ error: "room and event are required" });
    return;
  }

  const seqKey = `seq:${room}`;
  const listKey = `msgs:${room}`;

  try {
    const id = await kv.incr(seqKey);
    const entry = { id, event, data: data ?? null, ts: Date.now() };
    await kv.rpush(listKey, entry);
    await kv.ltrim(listKey, -500, -1); // keep the queue from growing forever

    res.status(200).json({ ok: true, id });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
}
