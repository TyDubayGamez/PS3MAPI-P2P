import { kv } from "@vercel/kv";

// Returns every event in the room with id > since, plus the highest id seen
// (pass that back in as `since` on your next poll).
export default async function handler(req, res) {
  const { room, since } = req.query;
  if (!room) {
    res.status(400).json({ error: "room is required" });
    return;
  }
  const sinceId = parseInt(since, 10) || 0;
  const listKey = `msgs:${room}`;

  try {
    const raw = await kv.lrange(listKey, 0, -1);
    const messages = [];
    let maxId = sinceId;

    for (const item of raw) {
      const entry = typeof item === "string" ? JSON.parse(item) : item;
      if (entry.id > sinceId) {
        messages.push(entry);
        if (entry.id > maxId) maxId = entry.id;
      }
    }

    res.status(200).json({ messages, nextSince: maxId });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
}
