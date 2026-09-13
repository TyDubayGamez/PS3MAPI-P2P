import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/router";
import * as Ably from "ably";

export default function Room() {
  const router = useRouter();
  const { code, username } = router.query;

  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [target, setTarget] = useState("");
  const [pid, setPid] = useState("0");
  const [address, setAddress] = useState("0");
  const [length, setLength] = useState("16");
  const [writeHex, setWriteHex] = useState("");

  const channelRef = useRef(null);
  const logEndRef = useRef(null);

  function log(entry) {
    setMessages((m) => [...m, entry]);
  }

  useEffect(() => {
    if (!code || !username) return;

    const client = new Ably.Realtime({
      authUrl: `/api/ably-auth?clientId=${encodeURIComponent(username)}`,
    });
    const channel = client.channels.get(`room-${code}`);
    channelRef.current = channel;

    channel.subscribe("chat", (msg) => {
      log({ type: "chat", from: msg.data.from, text: msg.data.text });
    });

    channel.subscribe("mem_read_response", (msg) => {
      if (msg.data.to !== username) return;
      log({
        type: "system",
        text: msg.data.error
          ? `Read failed from ${msg.data.from}: ${msg.data.error}`
          : `Read OK from ${msg.data.from}: ${msg.data.dataHex}`,
      });
    });

    channel.subscribe("mem_write_response", (msg) => {
      if (msg.data.to !== username) return;
      log({
        type: "system",
        text: msg.data.error
          ? `Write failed on ${msg.data.from}: ${msg.data.error}`
          : `Write OK on ${msg.data.from}`,
      });
    });

    channel.subscribe("presence_note", (msg) => {
      log({ type: "system", text: msg.data.text });
    });

    channel.publish("chat", { from: "system", text: `${username} joined the room.` });

    return () => {
      channel.unsubscribe();
      client.close();
    };
  }, [code, username]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function sendChat() {
    if (!chatInput.trim() || !channelRef.current) return;
    channelRef.current.publish("chat", { from: username, text: chatInput.trim() });
    setChatInput("");
  }

  function requestRead() {
    if (!channelRef.current || !target.trim()) return;
    channelRef.current.publish("mem_read_request", {
      from: username,
      to: target.trim(),
      pid: parseInt(pid, 16) || 0,
      address: address.trim(),
      length: parseInt(length, 10) || 0,
    });
    log({ type: "system", text: `Requested read from ${target}...` });
  }

  function requestWrite() {
    if (!channelRef.current || !target.trim()) return;
    channelRef.current.publish("mem_write_request", {
      from: username,
      to: target.trim(),
      pid: parseInt(pid, 16) || 0,
      address: address.trim(),
      dataHex: writeHex.trim(),
    });
    log({ type: "system", text: `Requested write on ${target}...` });
  }

  return (
    <main style={{ maxWidth: 720, margin: "40px auto", fontFamily: "sans-serif" }}>
      <h2>Room {code}</h2>
      <p style={{ color: "#666" }}>
        You are <b>{username}</b>. Reads/writes only work if the target has their
        Python agent running and approves the request.
      </p>

      <div
        style={{
          border: "1px solid #ddd",
          borderRadius: 8,
          padding: 12,
          height: 260,
          overflowY: "auto",
          background: "#fafafa",
        }}
      >
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 4 }}>
            {m.type === "chat" ? (
              <span>
                <b>{m.from}:</b> {m.text}
              </span>
            ) : (
              <span style={{ color: "#888", fontStyle: "italic" }}>{m.text}</span>
            )}
          </div>
        ))}
        <div ref={logEndRef} />
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <input
          style={{ flex: 1, padding: 8 }}
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendChat()}
          placeholder="Type a message..."
        />
        <button onClick={sendChat} style={{ padding: "8px 16px" }}>
          Send
        </button>
      </div>

      <div style={{ marginTop: 28, borderTop: "1px solid #ddd", paddingTop: 16 }}>
        <h3>Memory panel</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <label>
            Target username
            <input value={target} onChange={(e) => setTarget(e.target.value)} style={{ display: "block", width: "100%", padding: 6 }} />
          </label>
          <label>
            PID (hex)
            <input value={pid} onChange={(e) => setPid(e.target.value)} style={{ display: "block", width: "100%", padding: 6 }} />
          </label>
          <label>
            Address (hex)
            <input value={address} onChange={(e) => setAddress(e.target.value)} style={{ display: "block", width: "100%", padding: 6 }} />
          </label>
          <label>
            Length (read only)
            <input value={length} onChange={(e) => setLength(e.target.value)} style={{ display: "block", width: "100%", padding: 6 }} />
          </label>
        </div>
        <label style={{ display: "block", marginTop: 8 }}>
          Write data (hex, write only)
          <input value={writeHex} onChange={(e) => setWriteHex(e.target.value)} style={{ display: "block", width: "100%", padding: 6 }} />
        </label>
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <button onClick={requestRead} style={{ padding: "8px 16px" }}>
            Read
          </button>
          <button onClick={requestWrite} style={{ padding: "8px 16px" }}>
            Write
          </button>
        </div>
      </div>
    </main>
  );
}
