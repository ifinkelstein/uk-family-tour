'use strict';
const ASSETS = 'app/src/main/assets/tour';
const audioURL = f => `${ASSETS}/audio/` + f.replace(/^content\//, '').replace(/\.md$/, '.mp3');
const imgURL = (sid, i) => `${ASSETS}/images/${sid}-${i}.jpg`;

const el = document.getElementById('app');
const au = document.getElementById('au');

// A corrupted localStorage value must never brick the app at load time.
function loadJSON(k, fb) { try { return JSON.parse(localStorage.getItem(k)) ?? fb; } catch (_) { return fb; } }
function saveJSON(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) { } }

let MAN = null, ART = {}, kid = loadJSON('kid', true), GAP = 30000;
let queue = [], pos = -1, gapTimer = null, dragging = false, speed = 1.0;
let screen = { name: 'days' };
const heard = new Set(loadJSON('heard', []));

const speedList = [0.8, 1.0, 1.2, 1.5];
const cityVar = d => d <= 7 ? '--london' : d <= 12 ? '--edinburgh' : '--york';
const cityName = d => d <= 7 ? 'LONDON' : d <= 12 ? 'EDINBURGH' : 'YORK';
const accent = d => getComputedStyle(document.documentElement).getPropertyValue(cityVar(d)).trim();
const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
// For strings interpolated into inline onclick='...' JS: hex-escape everything
// non-alphanumeric so neither the JS string nor the HTML attribute can break.
const jsq = s => String(s).replace(/[^A-Za-z0-9 _.\-]/g, c => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0'));
const safeColor = c => /^#[0-9a-fA-F]{3,8}$/.test(c || '') ? c : '#888888';

function daysGroups() {
  const m = new Map();
  MAN.sights.forEach(s => { if (!m.has(s.day)) m.set(s.day, []); m.get(s.day).push(s); });
  return [...m.entries()].sort((a, b) => a[0] - b[0]);
}
const tracksOf = s => s.tracks[kid ? 'kid' : 'adult'];
const sightMinutes = s => Math.round(tracksOf(s).reduce((a, t) =>
  a + (t.est_minutes || 0) + (t.tell_me_more || []).reduce((x, c) => x + (c.est_minutes || 0), 0), 0));
const sightComplete = s => tracksOf(s).every(t => heard.has(t.file));

// ---- boot ----
async function boot() {
  // Register the SW before anything can fail, so the shell caches ASAP.
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => { });
  try {
    const r = await fetch(`${ASSETS}/manifest.json`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    MAN = await r.json();
  } catch (_) {
    el.innerHTML = `<div class="wrap" style="padding-top:80px;text-align:center">
      <div style="font-size:44px">📻</div>
      <h2 class="serif">Can't load the tour</h2>
      <p style="color:var(--muted)">Check wifi or signal, then try again.</p>
      <button class="retrybtn" onclick="location.reload()">Try again</button></div>`;
    return;
  }
  ART = await fetch(`${ASSETS}/images.json`).then(r => r.json()).catch(() => ({}));
  render();
}

// ---- audio ----
au.addEventListener('timeupdate', () => { if (!dragging) paintScrub(); });
// Keep the play/pause button honest when something else pauses the audio
// (phone call, unplugged headphones) and say so when a track can't load.
au.addEventListener('play', () => paintControls());
au.addEventListener('pause', () => paintControls());
au.addEventListener('playing', () => { setNotice(''); paintControls(); });
au.addEventListener('waiting', () => setNotice('Loading…'));
au.addEventListener('loadedmetadata', () => paintScrub());
au.addEventListener('error', () => {
  if (pos >= 0) setNotice("Couldn't load this story — is it downloaded? Try ⬇ over wifi.");
  paintControls();
});
let notice = '';
function setNotice(t) {
  notice = t;
  const n = document.getElementById('notice');
  if (n) { n.textContent = t; n.style.display = t ? '' : 'none'; }
}
au.addEventListener('ended', () => {
  const it = queue[pos]; if (it && !it.isMore) markHeard(it.file);
  if (pos + 1 < queue.length) startGap();
  else { paintControls(); }
});
function markHeard(f) { heard.add(f); saveJSON('heard', [...heard]); }

/* Walking gap: a story ends, the family strolls to the next spot, then the
   next story starts. The countdown is visible and skippable; chapters of the
   same deep dive chain after 1s; a hidden page (phone pocketed) chains
   immediately, because suspended timers would otherwise kill the tour. */
let gap = null; // { deadline, iv } while counting down
function startGap() {
  const len = document.hidden ? 0 : (queue[pos + 1].isMore ? 1000 : GAP);
  cancelGap();
  if (len < 1500) {
    if (len) gapTimer = setTimeout(() => setPos(pos + 1), len);
    else setPos(pos + 1);
    return;
  }
  gap = { deadline: Date.now() + len, iv: setInterval(paintGap, 1000) };
  gapTimer = setTimeout(advanceNow, len);
  paintPlayer();
}
function gapLeft() { return gap ? Math.max(0, Math.ceil((gap.deadline - Date.now()) / 1000)) : 0; }
function cancelGap() {
  clearTimeout(gapTimer);
  if (gap) { clearInterval(gap.iv); gap = null; }
}
function advanceNow() {
  const n = pos + 1;
  cancelGap();
  if (n < queue.length) setPos(n); else paintPlayer();
}
window.stayHere = () => { cancelGap(); paintPlayer(); };
document.addEventListener('visibilitychange', () => { if (document.hidden && gap) advanceNow(); });

function loadQueue(items, i = 0, day) {
  cancelGap();
  queue = items; setPos(i);
  if (day != null) cacheDay(day);
}
function setPos(i) {
  cancelGap();
  setNotice('');
  pos = i;
  au.src = audioURL(queue[i].file);
  au.playbackRate = speed;
  au.play().catch(() => { });
  updateMediaSession(queue[i]);
  saveResume();
  render(); // repaint lists too: auto-advance must move the highlight + now-playing title
}

// ---- resume where the family left off ----
let lastSaveT = 0;
function saveResume() {
  if (pos < 0 || !queue[pos]) return;
  saveJSON('resume', { screen, queue, pos, t: Math.floor(au.currentTime || 0), kid });
}
au.addEventListener('timeupdate', () => {
  const n = Date.now();
  if (n - lastSaveT > 5000) { lastSaveT = n; saveResume(); }
});
au.addEventListener('pause', saveResume);
window.resumeLast = () => {
  const rs = loadJSON('resume', null);
  if (!rs || !rs.queue || !rs.queue[rs.pos]) return;
  kid = !!rs.kid;
  if (rs.screen && rs.screen.name) screen = rs.screen;
  queue = rs.queue;
  const t = rs.t || 0;
  au.addEventListener('loadedmetadata', () => {
    if (t > 3 && au.duration && t < au.duration - 3) au.currentTime = t;
  }, { once: true });
  setPos(rs.pos);
};

// ---- lock-screen / earbud controls ----
function updateMediaSession(it) {
  if (!('mediaSession' in navigator) || !it) return;
  try {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: it.title,
      artist: it.sight || 'UK Family Tour',
      album: 'UK Family Tour',
      artwork: it.sid ? [{ src: imgURL(it.sid, 0), sizes: '512x512', type: 'image/jpeg' }] : [],
    });
  } catch (_) { }
}
if ('mediaSession' in navigator) {
  const ms = navigator.mediaSession;
  const set = (a, fn) => { try { ms.setActionHandler(a, fn); } catch (_) { } };
  set('play', () => playPause());
  set('pause', () => playPause());
  set('previoustrack', () => prev());
  set('nexttrack', () => next());
  set('seekto', d => { if (au.duration && d.seekTime != null) au.currentTime = d.seekTime; });
  set('seekbackward', d => { au.currentTime = Math.max(0, au.currentTime - (d.seekOffset || 10)); });
  set('seekforward', d => { if (au.duration) au.currentTime = Math.min(au.duration, au.currentTime + (d.seekOffset || 10)); });
}
function playPause() {
  if (gap) { advanceNow(); return; }          // during the gap, ▶ means "next story now"
  if (au.paused) {
    if (au.ended && pos + 1 < queue.length) { setPos(pos + 1); return; }
    au.play().catch(() => { });
  } else au.pause();
  paintControls();
}
function next() { if (pos + 1 < queue.length) setPos(pos + 1); }
function prev() { if (au.currentTime > 3 || pos === 0) au.currentTime = 0; else setPos(pos - 1); }
function seek(frac) { if (au.duration) au.currentTime = frac * au.duration; }
function cycleSpeed() { speed = speedList[(speedList.indexOf(speed) + 1) % speedList.length]; au.playbackRate = speed; paintControls(); }

// Find a base track by file across every sight and BOTH audiences, so the
// lookup still works mid-toggle and outside the sight screen.
function findBaseTrack(file) {
  for (const s of MAN.sights)
    for (const a of ['kid', 'adult'])
      for (const t of s.tracks[a]) if (t.file === file) return t;
  return null;
}
function tellMore() {
  const it = queue[pos]; if (!it) return;
  const base = findBaseTrack(it.file);
  const more = base && base.tell_me_more || [];
  if (!more.length) return;
  const items = more.map(c => ({ file: c.file, title: c.title, isMore: true, sight: it.sight, sid: it.sid }));
  queue.splice(pos + 1, 0, ...items);
  setPos(pos + 1);
}

// tell the service worker to pre-cache this whole day's audio for offline touring
// (BOTH audiences — the family toggles Kids/Grown-ups on one phone mid-walk)
function dayAudioURLs(day) {
  const urls = [];
  MAN.sights.filter(s => s.day === day).forEach(s =>
    ['kid', 'adult'].forEach(a => s.tracks[a].forEach(t => {
      urls.push(audioURL(t.file));
      (t.tell_me_more || []).forEach(c => urls.push(audioURL(c.file)));
    })));
  return urls.map(u => new URL(u, location.href).href);
}
function cacheDay(day) {
  if (!('serviceWorker' in navigator)) return;
  // .ready (not .controller) so this works on the very first visit too
  navigator.serviceWorker.ready.then(reg => {
    if (reg.active) reg.active.postMessage({ type: 'cacheDay', day, urls: dayAudioURLs(day) });
  }).catch(() => { });
}
window.saveDay = day => {
  const b = document.getElementById(`dl-${day}`);
  if (b) b.textContent = 'saving…';
  cacheDay(day);
};
if ('serviceWorker' in navigator) navigator.serviceWorker.addEventListener('message', e => {
  const d = e.data || {};
  if (d.type !== 'dayProgress') return;
  const b = document.getElementById(`dl-${d.day}`);
  if (!b) return;
  if (d.done + d.failed >= d.total) {
    b.textContent = d.failed ? `⚠ ${d.done}/${d.total}` : '✓ saved';
    if (!d.failed) b.classList.add('done');
  } else b.textContent = `${d.done}/${d.total}`;
});
// On the days screen, show which days are already fully saved for offline.
async function paintSavedBadges() {
  if (!('caches' in window) || !MAN) return;
  try {
    const c = await caches.open('audio-v1');
    const keys = new Set((await c.keys()).map(r => r.url));
    daysGroups().forEach(([day]) => {
      const b = document.getElementById(`dl-${day}`);
      if (!b) return;
      const urls = dayAudioURLs(day);
      const saved = urls.filter(u => keys.has(u)).length;
      if (saved >= urls.length) { b.textContent = '✓ saved'; b.classList.add('done'); }
      else if (saved > 0) b.textContent = `⬇ ${saved}/${urls.length}`;
    });
  } catch (_) { }
}

// ---- expand queues ----
function sightQueue(s) { return tracksOf(s).map(t => ({ file: t.file, title: t.title, isMore: false, sight: s.name, sid: s.id })); }
// Whole-day queue: base stories only. Deep dives are opt-in via Tell-me-more —
// pre-expanding every chapter made a day ~2.5h of mandatory audio.
function dayQueue(day) {
  const items = [];
  MAN.sights.filter(s => s.day === day).forEach(s =>
    tracksOf(s).forEach(t => {
      const moreMin = (t.tell_me_more || []).reduce((x, c) => x + (c.est_minutes || 0), 0);
      items.push({ file: t.file, title: t.title, isMore: false, sight: s.name, sid: s.id, moreMin });
    }));
  return items;
}

// ---- render ----
function render() {
  if (screen.name === 'days') renderDays();
  else if (screen.name === 'sight') renderSight(MAN.sights.find(s => s.id === screen.id));
  else if (screen.name === 'dayplay') renderDayPlay(screen.day);
  paintPlayer();
}
function toggleHTML() {
  return `<div class="toggle"><button class="${kid ? 'on' : ''}" onclick="setKid(true)">🧒 Kids</button>
    <button class="${!kid ? 'on' : ''}" onclick="setKid(false)">🧑 Grown-ups</button></div>`;
}
window.setKid = v => {
  if (v === kid) return;
  kid = v; saveJSON('kid', v);
  remapQueue();
  render();
};

/* Switching Kids/Grown-ups mid-tour used to leave the other mode's audio
   playing against the new mode's track list (and Tell-me-more no-oped).
   Rebuild the live queue in the new mode at the same story instead. */
function remapQueue() {
  if (pos < 0 || !queue.length) return;
  const active = gap || !au.ended || (au.paused && au.currentTime > 0);
  if (!active) return;
  const cur = queue[pos];
  const s0 = MAN.sights.find(x => x.id === cur.sid);
  if (!s0) { cancelGap(); return; }
  const multiSight = new Set(queue.map(it => it.sid)).size > 1;
  const items = multiSight ? dayQueue(s0.day) : sightQueue(s0);
  const baseOrdinal = Math.max(0, queue.slice(0, pos + 1).filter(it => !it.isMore).length - 1);
  const baseIdxs = items.map((it, i) => (it.isMore ? -1 : i)).filter(i => i >= 0);
  queue = items;
  setPos(baseIdxs[Math.min(baseOrdinal, baseIdxs.length - 1)] ?? 0);
}

function renderDays() {
  let h = `<div class="wrap"><div class="kicker">Our big trip · July 2026</div>
    <h1 class="title serif">London → Edinburgh → York</h1>${toggleHTML()}</div>`;
  if (needsA2HS()) {
    h += `<div class="a2hs">📲 On iPhone, tap <b>Share → Add to Home Screen</b> — then the whole tour works offline.
      <button onclick="dismissA2HS()">Got it</button></div>`;
  }
  const rs = pos < 0 ? loadJSON('resume', null) : null;
  if (rs && rs.queue && rs.queue[rs.pos]) {
    h += `<div class="resume" onclick="resumeLast()">▶&nbsp; Continue: <b>${esc(rs.queue[rs.pos].title)}</b>
      <span>${esc(rs.queue[rs.pos].sight || '')}</span></div>`;
  }
  daysGroups().forEach(([day, sights]) => {
    const a = accent(day);
    const today = isToday(sights[0].date);
    h += `<div class="dayhead${today ? ' today' : ''}" id="day-${day}"><span class="dot" style="background:${a}"></span>
      <span class="daylabel" style="color:${a}">Day ${day} · ${esc(sights[0].date || '')} · ${cityName(day)}</span>
      ${today ? '<span class="todaypill">TODAY</span>' : ''}
      <button class="dlbtn" id="dl-${day}" onclick="saveDay(${day})">⬇</button>
      <button class="playday" style="background:${a}22;color:${a}" onclick="openDayPlay(${day})">▶ Play day</button></div>`;
    sights.forEach(s => {
      const art = ART[s.id] || {};
      const img = imgURL(s.id, 0);
      const a2 = accent(day);
      h += `<div class="card" onclick="openSight('${jsq(s.id)}')">
        <img class="thumb" src="${img}" onerror="this.replaceWith(emojiThumb('${jsq(art.emoji || '📍')}','${safeColor(art.color)}'))">
        <div style="flex:1"><h3 class="serif">${esc(s.name)}</h3>
        <div class="sub">${esc(s.note || '')}</div>
        <div class="meta" style="color:${a2}">${tracksOf(s).length} stories · up to ${sightMinutes(s)} min${sightComplete(s) ? ' · ✓' : ''}</div></div>
        ${sightComplete(s) ? '<div class="stamp">✔</div>' : ''}</div>`;
    });
  });
  el.innerHTML = h;
  paintSavedBadges();
  // Once per launch, open the list at today's leg of the trip.
  if (!renderDays.scrolled) {
    const t = el.querySelector('.dayhead.today');
    if (t) { renderDays.scrolled = true; t.scrollIntoView({ block: 'start' }); }
  }
}
function needsA2HS() {
  return /iPhone|iPad|iPod/.test(navigator.userAgent)
    && !navigator.standalone
    && !matchMedia('(display-mode: standalone)').matches
    && !loadJSON('a2hsDismissed', false);
}
window.dismissA2HS = () => { saveJSON('a2hsDismissed', true); render(); };
const MONTHS = { Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5, Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11 };
function isToday(dateStr) {
  const m = /([A-Z][a-z]{2}) (\d{1,2})$/.exec(dateStr || '');
  if (!m) return false;
  const now = new Date();
  return MONTHS[m[1]] === now.getMonth() && Number(m[2]) === now.getDate();
}
window.emojiThumb = (emoji, color) => {
  const d = document.createElement('div'); d.className = 'thumb'; d.style.background = color; d.textContent = emoji; return d;
};

function renderSight(s) {
  const a = accent(s.day);
  document.documentElement.style.setProperty('--accent', a);
  const cur = queue[pos];
  const list = tracksOf(s).map((t, i) => {
    const on = cur && cur.file === t.file;
    const more = (t.tell_me_more || []).length;
    return `<div class="track ${on ? 'on' : ''}" onclick="playSightTrack('${jsq(s.id)}',${i})">
      <div class="tnum">${on ? '▶' : (heard.has(t.file) ? '✔' : (i + 1))}</div>
      <div style="flex:1"><h4 class="serif">${esc(t.title)}</h4>
      <div class="tm">≈ ${Math.round(t.est_minutes || 1)} min${more ? ` · +${Math.round((t.tell_me_more).reduce((x, c) => x + c.est_minutes, 0))} min more` : ''}</div></div></div>`;
  }).join('');
  el.innerHTML = `<div class="topbar"><button class="iconbtn" onclick="goDays()">←</button>
    <div style="flex:1"><h2 class="serif" style="margin:0">${esc(s.name)}</h2>
    <div class="daylabel" style="color:${a}">Day ${s.day} · ${esc(s.date || '')}</div></div>${toggleHTML()}</div>
    <div class="hero"><img src="${imgURL(s.id, 0)}" onerror="this.style.display='none'"></div>
    ${cur ? `<div class="nowtitle serif">${esc(cur.title)}</div>` : ''}
    <div>${list}</div>`;
}
window.playSightTrack = (sid, i) => {
  const s = MAN.sights.find(x => x.id === sid);
  loadQueue(sightQueue(s), i, s.day); render();
};

function renderDayPlay(day) {
  const a = accent(day);
  document.documentElement.style.setProperty('--accent', a);
  const items = queue.length ? queue : dayQueue(day);
  const rows = items.map((it, i) => `<div class="track ${pos === i ? 'on' : ''}" onclick="jump(${i})">
    <div class="tnum">${pos === i ? '▶' : (it.isMore ? '·' : i + 1)}</div>
    <div style="flex:1"><h4 class="serif" style="font-weight:${it.isMore ? 400 : 600}">${esc(it.title)}</h4>
    <div class="tm">${it.isMore ? 'deep dive · ' : ''}${esc(it.sight || '')}${!it.isMore && it.moreMin ? ` · +${Math.round(it.moreMin)} min extras` : ''}</div></div></div>`).join('');
  el.innerHTML = `<div class="topbar"><button class="iconbtn" onclick="goDays()">←</button>
    <div style="flex:1"><h2 class="serif" style="margin:0">Play the whole day</h2>
    <div class="daylabel" style="color:${a}">Day ${day} · ${cityName(day)} · ${items.length} stories</div></div>${toggleHTML()}</div>
    <div>${rows}</div>`;
}
window.jump = i => { setPos(i); render(); };
window.openDayPlay = day => { screen = { name: 'dayplay', day }; loadQueue(dayQueue(day), 0, day); render(); };
window.openSight = id => { screen = { name: 'sight', id }; render(); };
window.goDays = () => { screen = { name: 'days' }; render(); };

// ---- player bar ----
function paintPlayer() {
  const day = screen.day || (screen.id && MAN.sights.find(s => s.id === screen.id)?.day) || 2;
  const a = accent(day);
  const cur = queue[pos];
  // Tell-me-more works on both the sight screen and the whole-day player.
  const onPlayerScreen = screen.name === 'sight' || screen.name === 'dayplay';
  const base = onPlayerScreen && cur && !cur.isMore ? findBaseTrack(cur.file) : null;
  const inSight = !!(base && (base.tell_me_more || []).length);
  document.querySelectorAll('.player').forEach(n => n.remove());
  const bar = document.createElement('div'); bar.className = 'player';
  bar.innerHTML = `<div class="inner">
    <input type="range" id="scrub" min="0" max="1000" value="0" style="accent-color:${a}">
    <div class="times"><span id="tcur">0:00</span><span id="tdur"></span></div>
    <div class="notice" id="notice" style="display:${notice ? '' : 'none'}">${esc(notice)}</div>
    ${gap && queue[pos + 1] ? `<div class="gapchip">
      <span>Next: <b>${esc(queue[pos + 1].title)}</b> in <span id="gapleft">${gapLeft()}</span>s</span>
      <button class="gapstay" onclick="stayHere()">✕ stay</button></div>` : ''}
    ${inSight ? `<button class="tellmore" onclick="tellMore()">${kid ? '✨ Tell me MORE!' : 'Tell me more'}</button>` : ''}
    <div class="controls">
      <button class="speed" onclick="cycleSpeed()">${speed}×</button>
      <button onclick="prev()">⏮</button>
      <button class="play" onclick="playPause()" id="pp">▶</button>
      <button onclick="next()">⏭</button>
      <span class="mic">🎙</span>
    </div></div>`;
  document.body.appendChild(bar);
  const sc = bar.querySelector('#scrub');
  sc.addEventListener('input', () => { dragging = true; });
  sc.addEventListener('change', () => { seek(sc.value / 1000); dragging = false; });
  paintControls(); paintScrub();
}
function paintControls() {
  const pp = document.getElementById('pp'); if (pp) pp.textContent = au.paused ? '▶' : '⏸';
}
const fmtTime = s => { s = Math.max(0, Math.floor(s || 0)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
function paintScrub() {
  const sc = document.getElementById('scrub');
  if (sc && au.duration) sc.value = Math.round((au.currentTime / au.duration) * 1000);
  const tc = document.getElementById('tcur'), td = document.getElementById('tdur');
  if (tc) tc.textContent = fmtTime(au.currentTime);
  if (td) td.textContent = au.duration ? fmtTime(au.duration) : '';
}
function paintGap() {
  const g = document.getElementById('gapleft');
  if (g) g.textContent = gapLeft();
}
boot();
