export default function Home() {
  return (
    <main style={{ maxWidth: 480, margin: "80px auto", fontFamily: "sans-serif" }}>
      <h1>PS3 Mem Relay - backend</h1>
      <p style={{ color: "#666" }}>
        This Vercel deployment is a backend only (a Vercel KV-backed message
        queue for the desktop app). There's no web UI here - run the desktop
        app to actually use it.
      </p>
    </main>
  );
}
