"""Single-file dashboard served at "/" in demo mode. No build step, no framework.

All message text is inserted with textContent (never innerHTML) so a malicious
message can't inject script into the page.
"""

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Inbox-to-Action · {{BUSINESS}}</title>
<style>
  :root { --bg:#0e1116; --panel:#161b22; --line:#262d36; --text:#e6edf3; --muted:#8b949e;
          --accent:#3fb950; --warn:#d29922; --hot:#f85149; --blue:#58a6ff; }
  * { box-sizing:border-box; }
  body { margin:0; font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
         background:var(--bg); color:var(--text); }
  header { padding:20px 28px; border-bottom:1px solid var(--line); display:flex;
           justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; }
  h1 { font-size:18px; margin:0; } h1 span { color:var(--accent); }
  .muted { color:var(--muted); font-size:13px; }
  main { display:grid; grid-template-columns: 380px 1fr; gap:20px; padding:20px 28px; }
  @media (max-width: 900px) { main { grid-template-columns:1fr; } }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:16px; }
  .stats { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:16px; }
  .stat b { display:block; font-size:24px; }
  label { display:block; font-size:13px; color:var(--muted); margin:10px 0 4px; }
  input, textarea, select { width:100%; background:var(--bg); color:var(--text);
       border:1px solid var(--line); border-radius:6px; padding:8px 10px; font:inherit; }
  textarea { min-height:140px; resize:vertical; }
  button { margin-top:12px; background:var(--accent); color:#04130a; border:0; border-radius:6px;
           padding:9px 14px; font-weight:600; cursor:pointer; }
  button.ghost { background:transparent; color:var(--blue); border:1px solid var(--line); margin-right:6px; }
  .pill { display:inline-block; padding:1px 8px; border-radius:999px; font-size:12px;
          border:1px solid var(--line); margin-right:6px; }
  .high { color:var(--hot); border-color:var(--hot); }
  .medium { color:var(--warn); border-color:var(--warn); }
  .low { color:var(--muted); }
  .row { border-top:1px solid var(--line); padding:12px 0; }
  .row:first-child { border-top:0; }
  pre { white-space:pre-wrap; background:var(--bg); border:1px solid var(--line);
        border-radius:6px; padding:10px; font-size:13px; margin:8px 0 0; }
  #result { margin-top:14px; }
  a { color:var(--blue); }
</style>
</head>
<body>
<header>
  <div>
    <h1>Inbox-to-<span>Action</span></h1>
    <div class="muted">AI triage for <b>{{BUSINESS}}</b> · emails, web forms &amp; WhatsApp → sorted, summarised, routed</div>
  </div>
  <div class="muted" id="engine">…</div>
</header>
<main>
  <section>
    <div class="card">
      <b>Try it</b>
      <div class="muted">Paste any message. It's triaged live and not stored.</div>
      <div style="margin-top:8px">
        <button class="ghost" data-s="lead">Sample lead</button>
        <button class="ghost" data-s="angry">Angry customer</button>
        <button class="ghost" data-s="scam">Scam</button>
      </div>
      <label for="sender">From</label><input id="sender" value="tunde@bluepeak.ng">
      <label for="subject">Subject</label><input id="subject">
      <label for="channel">Channel</label>
      <select id="channel"><option>email</option><option>web_form</option><option>whatsapp</option></select>
      <label for="body">Message</label><textarea id="body"></textarea>
      <button id="go">Triage message</button>
      <div id="result"></div>
    </div>
  </section>
  <section>
    <div class="stats">
      <div class="card stat"><span class="muted">Processed</span><b id="s-total">0</b></div>
      <div class="card stat"><span class="muted">Needs a human</span><b id="s-human">0</b></div>
      <div class="card stat"><span class="muted">Sales leads</span><b id="s-leads">0</b></div>
    </div>
    <div class="card"><b>Recent messages</b><div id="list" class="muted">Loading…</div></div>
  </section>
</main>
<script>
const SAMPLES = {
  lead: {subject:"Quote for weekly deliveries", channel:"web_form",
    body:"Hi, I run a skincare brand in Lekki. We need about 40 deliveries a week across Lagos mainland and island. What are your rates? Budget is around N800k monthly.\n\nThanks,\nAmaka Obi"},
  angry: {subject:"Still waiting for my order!!", channel:"whatsapp",
    body:"This is unacceptable. My package was supposed to arrive Monday and it's still not here. I paid N45,000. I need a refund today or I'm going to report you."},
  scam: {subject:"CONGRATULATIONS!!!", channel:"email",
    body:"You have won $1,000,000 in our international lottery. Click here to claim your prize and verify your account now."}
};
const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

document.querySelectorAll("[data-s]").forEach(b => b.onclick = () => {
  const s = SAMPLES[b.dataset.s]; $("subject").value = s.subject; $("body").value = s.body; $("channel").value = s.channel;
});

function renderTriage(t, into) {
  into.replaceChildren();
  const head = el("div");
  head.append(el("span", "pill", t.category.replace("_"," ")), el("span", "pill " + t.urgency, t.urgency),
              el("span", "pill", Math.round(t.confidence*100) + "% sure"));
  if (t.needs_human) head.append(el("span", "pill high", "needs human"));
  into.append(head, el("div", null, t.summary));
  const facts = [];
  if (t.sender_name) facts.push("Sender: " + t.sender_name);
  if (t.company) facts.push("Company: " + t.company);
  if (t.amount != null) facts.push("Amount: " + (t.currency || "") + " " + Number(t.amount).toLocaleString());
  if (t.action_items && t.action_items.length) facts.push("Next: " + t.action_items.join("; "));
  if (facts.length) into.append(el("div", "muted", facts.join(" · ")));
  if (t.suggested_reply) into.append(el("pre", null, t.suggested_reply));
}

$("go").onclick = async () => {
  const out = $("result"); out.textContent = "Thinking…";
  try {
    const r = await fetch("/api/try", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({sender:$("sender").value || "anonymous", subject:$("subject").value,
                            body:$("body").value, channel:$("channel").value})});
    const data = await r.json();
    if (!r.ok) { out.textContent = data.detail ? JSON.stringify(data.detail) : "Error"; return; }
    renderTriage(data, out);
  } catch (e) { out.textContent = "Request failed: " + e; }
};

async function load() {
  const [h, s, m] = await Promise.all([fetch("/health"), fetch("/api/stats"), fetch("/api/messages?limit=25")]
    .map(p => p.then(r => r.json())));
  const names = {claude: "Claude", groq: "Groq", gemini: "Gemini"};
  $("engine").textContent = h.model ? "Engine: " + (names[h.engine] || h.engine) + " (" + h.model + ")" : "Engine: offline rules";
  $("s-total").textContent = s.total; $("s-human").textContent = s.needs_human;
  $("s-leads").textContent = s.by_category.sales_lead || 0;
  const list = $("list"); list.replaceChildren();
  if (!m.length) { list.textContent = "No messages yet. POST to /api/messages or run scripts/send_samples.py"; return; }
  m.forEach(p => {
    const row = el("div", "row");
    row.append(el("div", "muted", "#" + p.id + " · " + p.message.channel + " · " + p.message.sender + " · " + new Date(p.received_at).toLocaleString()));
    const body = el("div"); renderTriage(p.triage, body); row.append(body);
    list.append(row);
  });
}
load(); setInterval(load, 15000);
</script>
</body>
</html>
"""
