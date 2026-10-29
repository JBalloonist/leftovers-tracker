const $ = (sel) => document.querySelector(sel);
const views = ["list", "scan", "add", "detail", "print"];
let scanner = null;
let currentCode = null;
let currentItem = null;

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 401) { location.href = "/login"; return; }
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), 3000);
}

function ageDays(iso) {
  return Math.floor((Date.now() - new Date(iso)) / 86400000);
}

function ageText(iso) {
  const d = ageDays(iso);
  return d === 0 ? "today" : d === 1 ? "1 day" : `${d} days`;
}

function freshness(iso) {
  const d = ageDays(iso);
  return d <= 2 ? "fresh" : d <= 4 ? "aging" : "old";
}

function formatWhen(iso) {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

async function show(view) {
  if (scanner && view !== "scan") {
    await scanner.stop().catch(() => {});
    scanner = null;
  }
  views.forEach((v) => ($(`#view-${v}`).hidden = v !== view));
  if (view === "list") loadList();
  if (view === "scan") startScanner();
  if (view === "add") setTimeout(() => $("#name").focus(), 50);
}

async function loadList() {
  const items = await api("/api/items?active=1");
  const ul = $("#items");
  ul.innerHTML = "";
  $("#empty").hidden = items.length > 0;
  for (const it of items) {
    const li = document.createElement("li");
    li.className = `item ${freshness(it.stored_at)}`;
    li.innerHTML = `<span class="name"></span><span class="age"></span><span class="code small"></span>`;
    li.querySelector(".name").textContent = it.name;
    li.querySelector(".age").textContent = ageText(it.stored_at);
    li.querySelector(".code").textContent = it.label_code;
    li.onclick = () => openLabel(it.label_code);
    ul.appendChild(li);
  }
}

async function openLabel(raw) {
  const match = String(raw).toUpperCase().match(/LO-\d{4,}/);
  if (!match) { toast("That's not a leftovers label"); return; }
  try {
    const { code, item } = await api(`/api/labels/${match[0]}`);
    currentCode = code;
    currentItem = item;
    document.querySelectorAll(".code").forEach((el) => {
      if (el.closest("section")) el.textContent = code;
    });
    if (item) {
      $("#detail-name").textContent = item.name;
      $("#detail-when").textContent = `Stored ${formatWhen(item.stored_at)} (${ageText(item.stored_at)})`;
      show("detail");
    } else {
      $("#name").value = "";
      show("add");
    }
  } catch (e) {
    toast(e.message);
  }
}

function startScanner() {
  if (!window.Html5Qrcode) { toast("Scanner failed to load. Type the code instead."); return; }
  scanner = new Html5Qrcode("reader");
  scanner
    .start({ facingMode: "environment" }, { fps: 10, qrbox: 220 }, (text) => {
      if (navigator.vibrate) navigator.vibrate(50);
      openLabel(text);
    })
    .catch((err) => toast(`Camera unavailable: ${err}`));
}

// Voice input via Web Speech API (Safari exposes it as webkitSpeechRecognition).
// If it's missing, the iOS keyboard's own dictation mic still works in the text field.
function setupMic() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const mic = $("#mic");
  if (!SR) { mic.hidden = true; $("#mic-status").textContent = "Tip: use the keyboard's mic to dictate."; return; }
  let rec = null;
  mic.onclick = () => {
    if (rec) { rec.stop(); return; }
    rec = new SR();
    rec.lang = navigator.language || "en-US";
    rec.interimResults = true;
    rec.onresult = (e) => {
      $("#name").value = Array.from(e.results).map((r) => r[0].transcript).join("");
    };
    rec.onerror = (e) => ($("#mic-status").textContent = `Mic error: ${e.error}`);
    rec.onend = () => { rec = null; mic.classList.remove("listening"); $("#mic-status").textContent = ""; };
    mic.classList.add("listening");
    $("#mic-status").textContent = "Listening…";
    rec.start();
  };
}

$("#add-form").onsubmit = async (e) => {
  e.preventDefault();
  const name = $("#name").value.trim();
  if (!name) { toast("Enter a name"); return; }
  try {
    await api("/api/items", { method: "POST", body: { label_code: currentCode, name } });
    toast(`Saved ${name}`);
    show("list");
  } catch (err) { toast(err.message); }
};

document.querySelectorAll("[data-outcome]").forEach((btn) => {
  btn.onclick = async () => {
    try {
      await api(`/api/items/${currentItem.id}/remove`, { method: "POST", body: { outcome: btn.dataset.outcome } });
      toast(`${currentItem.name} marked ${btn.dataset.outcome}`);
      show("list");
    } catch (err) { toast(err.message); }
  };
});

$("#manual").onsubmit = (e) => { e.preventDefault(); openLabel($("#manual-code").value); };

document.querySelectorAll("[data-go]").forEach((el) => {
  el.onclick = (e) => { e.preventDefault(); show(el.dataset.go); };
});

setupMic();

// Arriving from a label scanned with the iPhone Camera app: /l/LO-0001 redirects to /?label=LO-0001
const fromLink = new URLSearchParams(location.search).get("label");
if (fromLink) {
  history.replaceState(null, "", "/");
  openLabel(fromLink);
} else {
  show("list");
}
