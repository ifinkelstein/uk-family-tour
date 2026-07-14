'use strict';
const ASSETS = 'app/src/main/assets/tour';
const audioURL = f => `${ASSETS}/audio/` + f.replace(/^content\//, '').replace(/\.md$/, '.mp3');
const imgURL = (sid, i) => `${ASSETS}/images/${sid}-${i}.jpg`;

const el = document.getElementById('app');
const au = document.getElementById('au');

let MAN = null, ART = {}, kid = true, GAP = 30000;
let queue = [], pos = -1, gapTimer = null, dragging = false, speed = 1.0;
let screen = { name: 'days' };
const heard = new Set(JSON.parse(localStorage.getItem('heard') || '[]'));

const speedList = [0.8, 1.0, 1.2, 1.5];
const cityVar = d => d <= 7 ? '--london' : d <= 12 ? '--edinburgh' : '--york';
const cityName = d => d <= 7 ? 'LONDON' : d <= 12 ? 'EDINBURGH' : 'YORK';
const accent = d => getComputedStyle(document.documentElement).getPropertyValue(cityVar(d)).trim();
const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

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
  MAN = await fetch(`${ASSETS}/manifest.json`).then(r => r.json());
  ART = await fetch(`${ASSETS}/images.json`).then(r => r.json()).catch(() => ({}));
  render();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => { });
}

// ---- audio ----
au.addEventListener('timeupdate', () => { if (!dragging) paintScrub(); });
au.addEventListener('ended', () => {
  const it = queue[pos]; if (it && !it.isMore) markHeard(it.file);
  if (pos + 1 < queue.length) { clearTimeout(gapTimer); gapTimer = setTimeout(() => setPos(pos + 1), GAP); }
  else { paintControls(); }
});
function markHeard(f) { heard.add(f); localStorage.setItem('heard', JSON.stringify([...heard])); }

function loadQueue(items, i = 0, day) {
  clearTimeout(gapTimer);
  queue = items; setPos(i);
  if (day != null) cacheDay(day);
}
function setPos(i) {
  clearTimeout(gapTimer);
  pos = i;
  au.src = audioURL(queue[i].file);
  au.playbackRate = speed;
  au.play().catch(() => { });
  paintPlayer();
}
function playPause() { if (au.paused) au.play().catch(() => { }); else { clearTimeout(gapTimer); au.pause(); } paintControls(); }
function next() { if (pos + 1 < queue.length) setPos(pos + 1); }
function prev() { if (au.currentTime > 3 || pos === 0) au.currentTime = 0; else setPos(pos - 1); }
function seek(frac) { if (au.duration) au.currentTime = frac * au.duration; }
function cycleSpeed() { speed = speedList[(speedList.indexOf(speed) + 1) % speedList.length]; au.playbackRate = speed; paintControls(); }

function tellMore() {
  const it = queue[pos]; if (!it) return;
  const s = MAN.sights.find(x => x.id === screen.id);
  const base = tracksOf(s).find(t => t.file === it.file);
  const more = base && base.tell_me_more || [];
  if (!more.length) return;
  const items = more.map(c => ({ file: c.file, title: c.title, isMore: true }));
  queue.splice(pos + 1, 0, ...items);
  setPos(pos + 1);
}

// tell the service worker to pre-cache this whole day's audio for offline touring
function cacheDay(day) {
  const sights = MAN.sights.filter(s => s.day === day);
  const urls = [];
  sights.forEach(s => tracksOf(s).forEach(t => {
    urls.push(audioURL(t.file));
    (t.tell_me_more || []).forEach(c => urls.push(audioURL(c.file)));
  }));
  if (navigator.serviceWorker && navigator.serviceWorker.controller)
    navigator.serviceWorker.controller.postMessage({ type: 'cacheDay', urls });
}

// ---- expand queues ----
function sightQueue(s) { return tracksOf(s).map(t => ({ file: t.file, title: t.title, isMore: false })); }
function dayQueue(day) {
  const items = [];
  MAN.sights.filter(s => s.day === day).forEach(s =>
    tracksOf(s).forEach(t => {
      items.push({ file: t.file, title: t.title, isMore: false, sight: s.name });
      (t.tell_me_more || []).forEach(c => items.push({ file: c.file, title: c.title, isMore: true, sight: s.name }));
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
window.setKid = v => { kid = v; render(); };

function renderDays() {
  let h = `<div class="wrap"><div class="kicker">Our big trip · July 2026</div>
    <h1 class="title serif">London → Edinburgh → York</h1>${toggleHTML()}</div>`;
  daysGroups().forEach(([day, sights]) => {
    const a = accent(day);
    h += `<div class="dayhead"><span class="dot" style="background:${a}"></span>
      <span class="daylabel" style="color:${a}">Day ${day} · ${esc(sights[0].date || '')} · ${cityName(day)}</span>
      <button class="playday" style="background:${a}22;color:${a}" onclick="openDayPlay(${day})">▶ Play day</button></div>`;
    sights.forEach(s => {
      const art = ART[s.id] || {};
      const img = imgURL(s.id, 0);
      const a2 = accent(day);
      h += `<div class="card" onclick="openSight('${s.id}')">
        <img class="thumb" src="${img}" onerror="this.replaceWith(emojiThumb('${esc(art.emoji || '📍')}','${art.color || '#888'}'))">
        <div style="flex:1"><h3 class="serif">${esc(s.name)}</h3>
        <div class="sub">${esc(s.note || '')}</div>
        <div class="meta" style="color:${a2}">${tracksOf(s).length} stories · up to ${sightMinutes(s)} min${sightComplete(s) ? ' · ✓' : ''}</div></div>
        ${sightComplete(s) ? '<div class="stamp">✔</div>' : ''}</div>`;
    });
  });
  el.innerHTML = h;
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
    return `<div class="track ${on ? 'on' : ''}" onclick="playSightTrack('${s.id}',${i})">
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
    <div class="tm">${it.isMore ? 'deep dive · ' : ''}${esc(it.sight || '')}</div></div></div>`).join('');
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
  const inSight = screen.name === 'sight' && cur && !cur.isMore;
  document.querySelectorAll('.player').forEach(n => n.remove());
  const bar = document.createElement('div'); bar.className = 'player';
  bar.innerHTML = `<div class="inner">
    <input type="range" id="scrub" min="0" max="1000" value="0" style="accent-color:${a}">
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
function paintScrub() {
  const sc = document.getElementById('scrub');
  if (sc && au.duration) sc.value = Math.round((au.currentTime / au.duration) * 1000);
}
boot();
