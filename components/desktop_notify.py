"""
components/desktop_notify.py - Desktop notifications and a reminder chime.

notify() runs in a tiny frame on every reminder check. For each call not alerted
before on this computer it (1) shows a system notification if allowed and
(2) asks the sidebar control to play a chime. The sidebar control is a frame
that stays loaded, so once the user has clicked it (or anywhere in the app)
its audio is unlocked and it can play sounds later.
"""
import json
import time

import streamlit as st


def _frame(markup: str, height: int):
    """Same-origin iframe running our script (st.iframe replaces components.html in newer Streamlit)."""
    if hasattr(st, "iframe"):
        st.iframe(markup, height=max(height, 1))
    else:  # older Streamlit
        import streamlit.components.v1 as components
        components.html(markup, height=height)

STORE_KEY = "sscrm_notified_v1"
CHIME_KEY = "sscrm_chime"
SOUND_KEY = "sscrm_sound"


def notify(items: list):
    """items: [{"tag", "title", "body"}]. Alerts each tag once per computer."""
    if not items:
        return
    payload = json.dumps(items)
    # The run stamp changes the frame on every check so the browser re-runs it.
    _frame(f"""
<!-- run {time.time():.0f} -->
<script>
(function () {{
  const items = {payload};
  const load = (k) => {{ try {{ return JSON.parse(localStorage.getItem(k) || "{{}}"); }} catch (e) {{ return {{}}; }} }};
  const shown = load("{STORE_KEY}"), rung = load("{STORE_KEY}_sound");
  const now = Date.now();
  [shown, rung].forEach(m => {{ for (const k in m) if (now - m[k] > 2 * 86400000) delete m[k]; }});
  const canShow = ("Notification" in window) && Notification.permission === "granted";
  let ring = false;
  items.forEach(function (it) {{
    if (canShow && !shown[it.tag]) {{
      try {{
        const n = new Notification(it.title, {{ body: it.body, tag: it.tag, requireInteraction: true, renotify: true }});
        n.onclick = function () {{ try {{ window.top.focus(); }} catch (e) {{}} try {{ window.parent.focus(); }} catch (e) {{}} n.close(); }};
        shown[it.tag] = now;
      }} catch (e) {{ console.log("notification failed", e); }}
    }}
    if (!rung[it.tag]) {{ rung[it.tag] = now; ring = true; }}
  }});
  try {{
    localStorage.setItem("{STORE_KEY}", JSON.stringify(shown));
    localStorage.setItem("{STORE_KEY}_sound", JSON.stringify(rung));
    if (ring && localStorage.getItem("{SOUND_KEY}") !== "off") localStorage.setItem("{CHIME_KEY}", String(now));
  }} catch (e) {{}}
}})();
</script>""", 0)


def permission_control():
    """Sidebar: desktop alerts on/off + test, sound on/off + test. Also the chime player."""
    _frame(f"""
<div style="font-family:'Inter',system-ui,sans-serif; font-size:12.5px; color:#FFFFFF; line-height:1.4;">
  <div style="display:flex; gap:6px;">
    <button id="b" style="flex:1; padding:9px 8px; border:1px solid rgba(255,255,255,0.35); border-radius:10px;
       background:rgba(255,255,255,0.12); color:#FFFFFF; font-weight:700; font-size:12.5px; cursor:pointer;"></button>
    <button id="snd" title="Reminder sound" style="width:44px; border:1px solid rgba(255,255,255,0.35); border-radius:10px;
       background:rgba(255,255,255,0.12); color:#FFFFFF; font-size:16px; cursor:pointer;"></button>
  </div>
  <div id="s" style="margin-top:6px; color:#C9D8F2;"></div>
</div>
<script>
const b = document.getElementById("b"), s = document.getElementById("s"), snd = document.getElementById("snd");
let ctx = null;
function unlock() {{
  try {{ ctx = ctx || new (window.AudioContext || window.webkitAudioContext)(); if (ctx.state === "suspended") ctx.resume(); }} catch (e) {{}}
}}
function chime() {{
  if (localStorage.getItem("{SOUND_KEY}") === "off") return;
  unlock(); if (!ctx) return;
  const t0 = ctx.currentTime + 0.05;
  [[880, 0], [1175, 0.18], [1568, 0.36], [880, 0.9], [1175, 1.08], [1568, 1.26]].forEach(function (n) {{
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = "sine"; o.frequency.value = n[0];
    g.gain.setValueAtTime(0.0001, t0 + n[1]);
    g.gain.exponentialRampToValueAtTime(0.35, t0 + n[1] + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + n[1] + 0.32);
    o.connect(g); g.connect(ctx.destination); o.start(t0 + n[1]); o.stop(t0 + n[1] + 0.35);
  }});
}}
window.addEventListener("storage", function (e) {{ if (e.key === "{CHIME_KEY}") chime(); }});
try {{ window.parent.document.addEventListener("pointerdown", unlock, {{ capture: true }}); }} catch (e) {{}}
document.addEventListener("pointerdown", unlock, {{ capture: true }});

function render() {{
  const soundOn = localStorage.getItem("{SOUND_KEY}") !== "off";
  snd.textContent = soundOn ? "🔊" : "🔇";
  snd.title = soundOn ? "Reminder sound on (click to turn off)" : "Reminder sound off (click to turn on)";
  const iOS = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const homeScreen = window.navigator.standalone === true || window.matchMedia("(display-mode: standalone)").matches;
  if (iOS && !homeScreen) {{ b.textContent = "🔊 Test reminder sound";
    s.textContent = "iPhone/iPad: for pop-up alerts, open the CRM from the Home Screen (Share → Add to Home Screen)."; return; }}
  if (!("Notification" in window)) {{ b.textContent = "🔊 Test reminder sound"; s.textContent = "This browser can't show desktop alerts; sound still works."; return; }}
  const p = Notification.permission;
  if (p === "granted") {{ b.textContent = "🔔 Alerts on · test"; s.textContent = "Reminders pop up with a sound, even outside the browser."; }}
  else if (p === "denied") {{ b.textContent = "🔊 Test reminder sound";
    s.innerHTML = "🔕 Desktop pop-ups are blocked: click 🔒 left of the address bar → Notifications → Allow, then reload."; }}
  else {{ b.textContent = "🔔 Turn on desktop alerts"; s.textContent = "Get call reminders even when the CRM isn't the active window."; }}
}}
b.onclick = async function () {{
  unlock();
  if ("Notification" in window && Notification.permission === "default") {{
    try {{ await Notification.requestPermission(); }} catch (e) {{}}
  }}
  if ("Notification" in window && Notification.permission === "granted") {{
    const n = new Notification("Sidharth CRM", {{ body: "Alerts are working. Call reminders will appear like this, with a sound." }});
    n.onclick = function () {{ try {{ window.top.focus(); }} catch (e) {{}} n.close(); }};
  }}
  chime(); render();
}};
snd.onclick = function () {{
  unlock();
  const on = localStorage.getItem("{SOUND_KEY}") !== "off";
  localStorage.setItem("{SOUND_KEY}", on ? "off" : "on");
  render(); if (!on) chime();
}};
render();
</script>""", 118)
