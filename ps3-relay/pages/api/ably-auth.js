import Ably from "ably";

// Issues short-lived Ably tokens to clients (browser or Python agent) so the
// real API key never leaves the server. clientId is just a display name here
// since this is a private/trusted-friends tool, not a real auth system.
export default async function handler(req, res) {
  if (!process.env.ABLY_API_KEY) {
    res.status(500).json({ error: "ABLY_API_KEY is not set on the server." });
    return;
  }

  const client = new Ably.Rest(process.env.ABLY_API_KEY);
  const clientId = (req.query.clientId || "anonymous").toString().slice(0, 64);

  try {
    const tokenRequestData = await client.auth.createTokenRequest({ clientId });
    res.status(200).json(tokenRequestData);
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
}
