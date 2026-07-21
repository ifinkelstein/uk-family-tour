'use strict';
const ASSETS = 'tour';
// Narration audio path is voice-dependent: Kokoro ships under tour/audio/,
// other voices (e.g. Gemini) under tour/audio-<voice>/ once their assets land.
const audioURL = f => `${ASSETS}/${voiceDir()}/` + f.replace(/^content\//, '').replace(/\.md$/, '.mp3');
const imgURL = (sid, i) => `${ASSETS}/images/${sid}-${i}.jpg`;
const mapURL = id => `${ASSETS}/maps/${id}${id.endsWith('-indoor') ? '.svg' : '.png'}`;
const INDOOR_MAPS = ['day06-churchill-war-rooms', 'day07-hampton-court'];
const DAY_MAPS = [3, 5, 6, 9];
const readingFile = (s, ext) => `${String(s.day).padStart(2, '0')} ${s.name} - ${kid ? 'Kids' : 'Grown-ups'}.${ext}`;
const readingURL = (s, ext) => `${ext === 'pdf' ? 'reading-pdfs' : 'reading-epubs'}/${encodeURIComponent(readingFile(s, ext))}`;
// Media drawer: photos, short films and period music per sight, tagged to a
// chapter (1-based base-track index). Assets live under tour/media/<sid>/.
const mediaURL = (sid, f) => `${ASSETS}/media/${sid}/${f}`;
const MEDIA_SIGHTS = ['day11-stirling-castle', 'day11-stirling-town-walk', 'day09-literary-edinburgh',
  'day02-richmond-park', 'day03-city-walk', 'day04-greenwich', 'day05-british-museum',
  'day06-buckingham-palace', 'day07-hampton-court', 'day08-train-north', 'day10-inchcolm-island',
  'day12-arthurs-seat', 'day13-york', 'day14-jorvik', 'day09-edinburgh-castle', 'day09-whisky']; // sights that ship a media/<id>.json

const el = document.getElementById('app');
const au = document.getElementById('au');

// A corrupted localStorage value must never brick the app at load time.
function loadJSON(k, fb) { try { return JSON.parse(localStorage.getItem(k)) ?? fb; } catch (_) { return fb; } }
function saveJSON(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) { } }

let MAN = null, ART = {}, MON = null, kid = loadJSON('kid', true), GAP = 30000;
let queue = [], pos = -1, gapTimer = null, dragging = false, speed = loadJSON('speed', 1.0);
let theme = loadJSON('theme', 'auto');   // 'auto' | 'light' | 'dark'
let voice = loadJSON('voice', 'kokoro'); // narration voice engine
let settingsConfirm = null;              // inline "tap again to confirm" state on the settings screen
let announceToken = 0;
let screen = { name: 'days' };
let MEDIA = {};             // sid -> media manifest (null once known to be absent)
const mediaLoading = {};    // sid -> in-flight promise, to dedupe concurrent loads
let mediaStash = null;      // saved narration state while a music clip plays
let mScreen = null;         // open media drawer state: { sid, chapter, openId }
const heard = new Set(loadJSON('heard', []));

const speedList = [0.8, 1.0, 1.2, 1.5];

// ---- narration voice ----
// Kokoro is always bundled. Extra voices show up in Settings only once the
// manifest advertises them (MAN.voices = ['gemini', …]) AND their audio dir
// exists — until then the selector stays hidden, per "when such assets avail".
const VOICES = {
  kokoro: { name: 'Kokoro', dir: 'audio', note: 'Warm, natural narration. Bundled with the tour.' },
  gemini: { name: 'Gemini', dir: 'audio-gemini', note: "Google Gemini voices — a brighter, more expressive read." },
};
const voiceAvailable = id => id === 'kokoro' || (Array.isArray(MAN?.voices) && MAN.voices.includes(id));
const availableVoices = () => Object.keys(VOICES).filter(voiceAvailable);
// Fall back to Kokoro if a previously-chosen voice is no longer available.
function voiceDir() { const v = voiceAvailable(voice) ? voice : 'kokoro'; return VOICES[v].dir; }

// ---- theme ----
// 'auto' defers to the OS (prefers-color-scheme); light/dark force via a
// data-theme attribute the stylesheet keys off of.
function applyTheme() {
  const r = document.documentElement;
  if (theme === 'light' || theme === 'dark') r.setAttribute('data-theme', theme);
  else r.removeAttribute('data-theme');
}
const cityVar = d => d <= 7 ? '--london' : d <= 12 ? '--edinburgh' : '--york';
const cityName = d => d <= 7 ? 'LONDON' : d <= 12 ? 'EDINBURGH' : 'YORK';
const accent = d => getComputedStyle(document.documentElement).getPropertyValue(cityVar(d)).trim();
const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
// For strings interpolated into inline onclick='...' JS: hex-escape everything
// non-alphanumeric so neither the JS string nor the HTML attribute can break.
const jsq = s => String(s).replace(/[^A-Za-z0-9 _.\-]/g, c => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0'));
const safeColor = c => /^#[0-9a-fA-F]{3,8}$/.test(c || '') ? c : '#888888';
const displayTitle = s => String(s || '').replace(/^\s*Tell Me More:\s*/i, '');
const chaptersOf = t => t.tell_me_more || [];
const trackMinutes = t => (t.est_minutes || 0) + chaptersOf(t).reduce((x, c) => x + (c.est_minutes || 0), 0);
const trackFiles = t => [t.file, ...chaptersOf(t).map(c => c.file)];
const sightFiles = s => tracksOf(s).flatMap(trackFiles);

function daysGroups() {
  const m = new Map();
  MAN.sights.forEach(s => { if (!m.has(s.day)) m.set(s.day, []); m.get(s.day).push(s); });
  return [...m.entries()].sort((a, b) => a[0] - b[0]);
}
const tracksOf = s => s.tracks[kid ? 'kid' : 'adult'];
const sightMinutes = s => Math.round(tracksOf(s).reduce((a, t) => a + trackMinutes(t), 0));
const sightComplete = s => sightFiles(s).every(f => heard.has(f));
const expandedCount = s => sightFiles(s).length;

// ---- boot ----
async function boot() {
  applyTheme();
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
  MON = await fetch(`${ASSETS}/monarchy.json`).then(r => r.json()).catch(() => null);
  MEDIA_SIGHTS.forEach(loadMedia); // fire-and-forget so galleries + offline pre-cache are ready
  render();
}

// ---- media drawer data ----
function loadMedia(sid) {
  if (sid in MEDIA) return Promise.resolve(MEDIA[sid]);
  if (mediaLoading[sid]) return mediaLoading[sid];
  mediaLoading[sid] = (async () => {
    let v = null;
    try { const r = await fetch(`${ASSETS}/media/${sid}.json`); v = r.ok ? await r.json() : null; }
    catch (_) { v = null; }
    MEDIA[sid] = v; delete mediaLoading[sid];
    if (screen.name === 'sight' && screen.id === sid) render(); // reveal the gallery once loaded
    return v;
  })();
  return mediaLoading[sid];
}
const mediaCaption = it => (kid && it.kidcaption) ? it.kidcaption : it.caption;
const chapterLabel = (m, ch) => (m.chapters.find(c => c.n === ch) || {}).label || `Chapter ${ch}`;
function mediaItems(sid, ch) { const m = MEDIA[sid]; if (!m) return []; return ch ? m.items.filter(i => i.chapter === ch) : m.items; }
function mediaChipText(items) {
  const c = { image: 0, video: 0, audio: 0 }; items.forEach(i => c[i.type]++);
  const p = []; if (c.image) p.push(`🖼 ${c.image}`); if (c.video) p.push(`🎬 ${c.video}`); if (c.audio) p.push(`♪ ${c.audio}`);
  return p.join('  ·  ');
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
  const it = queue[pos];
  if (it && it.isMedia) { // music never auto-advances into the tour
    if (mediaStash) setNotice('Music finished — tap ↩ Back to the tour to return.');
    paintPlayer();
    return;
  }
  if (it) markHeard(it.file);
  const nxt = queue[pos + 1];
  if (nxt && nxt.isMore) startGap();   // chain this story's sub-chapters
  else {
    // Story complete: stop rather than run into the next main story.
    // Play (or next) resumes with the next story when the family is ready.
    if (nxt) setNotice(`Story complete — up next: ${nxt.title}`);
    paintPlayer();
  }
});
function markHeard(f) { heard.add(f); saveJSON('heard', [...heard]); }

/* Sub-chapter chain: within one story, child chapters follow after a short
   beat (immediately when the phone is pocketed). Playback never crosses into
   the NEXT main story on its own — see the 'ended' handler. */
let gap = null; // { deadline, iv } while counting down (legacy long-gap UI)
function startGap() {
  const len = document.hidden ? 0 : 1000;
  cancelGap();
  if (len) gapTimer = setTimeout(() => setPos(pos + 1), len);
  else setPos(pos + 1);
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
  announceToken++;
  if ('speechSynthesis' in window) speechSynthesis.cancel();
  pos = i;
  au.src = queue[i].src || audioURL(queue[i].file); // media clips carry a direct src
  au.playbackRate = queue[i].isMedia ? 1.0 : speed;
  updateMediaSession(queue[i]);
  saveResume();
  render(); // repaint lists too: auto-advance must move the highlight + now-playing title
  announceThenPlay(queue[i], announceToken);
}

function announceThenPlay(it, token) {
  // Headings are baked into each track's audio (spoken title before the
  // narration, same voice) — no browser TTS, so clips never overlap.
  if (token !== announceToken) return;
  if (it?.isMore) {
    setNotice(`Next chapter: ${it.title}`);
    setTimeout(() => { if (token === announceToken) setNotice(''); }, 4000);
  } else {
    setNotice('');
  }
  au.play().catch(() => { });
}

// ---- map overlay ----
window.showMap = (id, title) => {
  const ov = document.createElement('div');
  ov.className = 'mapoverlay';
  ov.innerHTML = `<div class="mapbar"><span>${esc(title || 'Map')}</span>
    <button class="iconbtn" onclick="this.closest('.mapoverlay').remove()">✕</button></div>
    <div class="mapscroll"><img src="${mapURL(id)}" alt="map"></div>`;
  ov.addEventListener('click', e => { if (e.target === ov) ov.remove(); });
  document.body.appendChild(ov);
};

// ---- media drawer (gallery of photos, films and period music) ----
window.openMedia = (sid, chapter) => { mScreen = { sid, chapter: chapter || 0, openId: null }; drawMedia(); };
window.closeMedia = () => { mScreen = null; document.querySelector('.mediaoverlay')?.remove(); };
window.mFilter = ch => { if (mScreen) { mScreen.chapter = ch; mScreen.openId = null; drawMedia(); } };
window.mOpen = id => { if (mScreen) { mScreen.openId = id; drawMedia(); } };
window.mBack = () => { if (mScreen) { mScreen.openId = null; drawMedia(); } };

function drawMedia() {
  const m = MEDIA[mScreen.sid]; if (!m) return;
  document.querySelector('.mediaoverlay')?.remove();
  const ov = document.createElement('div'); ov.className = 'mediaoverlay';
  ov.innerHTML = mScreen.openId ? mediaDetailHTML(m) : mediaGridHTML(m);
  ov.addEventListener('click', e => { if (e.target === ov) closeMedia(); });
  document.body.appendChild(ov);
  const grid = ov.querySelector('.mgrid'); if (grid) grid.scrollTop = 0;
}
function mediaGridHTML(m) {
  const sid = mScreen.sid, cur = mScreen.chapter;
  const chip = (n, label) => `<button class="mfchip ${cur === n ? 'on' : ''}" onclick="mFilter(${n})">${esc(label)}</button>`;
  const chips = [chip(0, 'All')].concat(m.chapters.map(c => chip(c.n, `${c.n}. ${c.label}`))).join('');
  const items = mediaItems(sid, cur || 0);
  const tiles = items.map(it => mediaTileHTML(sid, it)).join('') ||
    `<div class="mempty">No media for this chapter.</div>`;
  return `<div class="mbar"><div class="mbartitle"><b>${esc(m.name)}</b><span>${esc(m.title)}</span></div>
    <button class="iconbtn mclose" onclick="closeMedia()">✕</button></div>
    <div class="mfilters">${chips}</div>
    <div class="mgrid">${tiles}</div>`;
}
function mediaTileHTML(sid, it) {
  const cap = it.type === 'image' ? mediaCaption(it) : (it.title || mediaCaption(it));
  const art = it.type === 'audio'
    ? `<span class="mtileart maudio">♪</span>`
    : `<img class="mtileart" loading="lazy" src="${it.type === 'image' ? mediaURL(sid, it.file) : esc(it.thumb)}" onerror="this.style.visibility='hidden'">`;
  const badge = it.type === 'video' ? '<span class="mbadge">▶</span>'
    : it.type === 'audio' ? '<span class="mbadge">♪</span>' : '';
  return `<button class="mtile mt-${it.type}" onclick="mOpen('${jsq(it.id)}')">
    <span class="mtileimg">${art}${badge}</span>
    <span class="mtcap">${esc(cap)}</span></button>`;
}
function mediaDetailHTML(m) {
  const sid = mScreen.sid, it = m.items.find(x => x.id === mScreen.openId);
  if (!it) return mediaGridHTML(m);
  const credit = `<div class="mcredit">${esc(it.credit || '')}${it.license ? ` · ${esc(it.license)}` : ''}${it.source ? ` · <a href="${esc(it.source)}" target="_blank" rel="noopener">source ↗</a>` : ''}</div>`;
  const listen = `<button class="listenbtn" onclick="playChapter('${jsq(sid)}',${it.chapter})">▶ Listen to this story</button>`;
  let body;
  if (it.type === 'image') {
    body = `<div class="mdimg"><img src="${mediaURL(sid, it.file)}" alt=""></div>`;
  } else if (it.type === 'video') {
    body = `<div class="mdvideo"><iframe src="https://www.youtube-nocookie.com/embed/${esc(it.youtube_id)}?autoplay=1&rel=0&playsinline=1"
      title="${esc(it.title || '')}" allow="autoplay; encrypted-media; fullscreen; picture-in-picture" allowfullscreen></iframe></div>`;
  } else {
    body = `<div class="mdaudio"><div class="mdaudioart">♪</div>
      <button class="mplaybtn" onclick="playMediaAudio('${jsq(sid)}','${jsq(it.id)}')">▶ Play music</button>
      <div class="mdhint">Plays in the bar below — tap <b>↩ Back to the tour</b> there to return to the story.</div></div>`;
  }
  return `<div class="mbar"><button class="iconbtn" onclick="mBack()">←</button>
    <div class="mbartitle"><b>${esc(it.title || m.name)}</b><span>${esc(chapterLabel(m, it.chapter))}</span></div>
    <button class="iconbtn mclose" onclick="closeMedia()">✕</button></div>
    <div class="mdetail">${body}
      <div class="mdcap">${esc(mediaCaption(it))}</div>
      ${credit}
      <div class="mdactions">${listen}</div></div>`;
}
// Jump from a media tile straight into the audio story it illustrates.
window.playChapter = (sid, ch) => {
  const s = MAN.sights.find(x => x.id === sid); if (!s) return;
  const items = sightQueue(s);
  const base = tracksOf(s)[ch - 1];
  const idx = base ? Math.max(0, items.findIndex(it => it.file === base.file)) : 0;
  screen = { name: 'sight', id: sid };
  closeMedia();
  loadQueue(items, idx, s.day); render(); window.scrollTo(0, 0);
};
// Play a short atmospheric music clip through the main player, remembering the
// narration so the family can pop back with one tap.
window.playMediaAudio = (sid, id) => {
  const m = MEDIA[sid]; if (!m) return;
  const it0 = m.items.find(x => x.id === id); if (!it0) return;
  const c = queue[pos];
  if (c && !c.isMedia) mediaStash = { queue: queue.slice(), pos, t: au.currentTime || 0, screen: { ...screen } };
  const s = MAN.sights.find(x => x.id === sid);
  closeMedia();
  loadQueue([{
    src: mediaURL(sid, it0.file), title: it0.title, sight: (s && s.name) || m.name,
    sid, isMedia: true, num: '♪', mediaChapter: it0.chapter
  }], 0, s ? s.day : undefined);
};
window.backToTour = () => {
  const st = mediaStash; mediaStash = null;
  if (!st) { au.pause(); queue = []; pos = -1; setNotice(''); render(); return; }
  if (st.screen) screen = st.screen;
  queue = st.queue;
  const t = st.t || 0;
  au.addEventListener('loadedmetadata', function h() {
    if (t > 1 && au.duration && t < au.duration - 1) au.currentTime = t;
    au.removeEventListener('loadedmetadata', h);
  }, { once: true });
  setPos(st.pos);
  render();
};

// ---- resume where the family left off ----
let lastSaveT = 0;
function saveResume() {
  if (pos < 0 || !queue[pos] || queue[pos].isMedia) return; // don't resume into a music clip
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
function cycleSpeed() { setSpeedPref(speedList[(speedList.indexOf(speed) + 1) % speedList.length]); }
function setSpeedPref(v) {
  speed = v; saveJSON('speed', v);
  if (!(queue[pos] && queue[pos].isMedia)) au.playbackRate = v;
  const b = document.querySelector('.player .speed'); if (b) b.textContent = `${v}×`;
  if (screen.name === 'settings') renderSettings();
}

// tell the service worker to pre-cache this whole day's audio for offline touring
// (BOTH audiences — the family toggles Kids/Grown-ups on one phone mid-walk)
function dayAudioURLs(day) {
  const urls = [];
  MAN.sights.filter(s => s.day === day).forEach(s => {
    ['kid', 'adult'].forEach(a => s.tracks[a].forEach(t => {
      urls.push(audioURL(t.file));
      (t.tell_me_more || []).forEach(c => urls.push(audioURL(c.file)));
    }));
    // maps ride along so the ⬇ button makes the whole day work offline
    urls.push(mapURL(s.id));
    if (INDOOR_MAPS.includes(s.id)) urls.push(mapURL(s.id + '-indoor'));
  });
  if (DAY_MAPS.includes(day)) urls.push(mapURL(`day-${String(day).padStart(2, '0')}`));
  // Gallery images + music ride along so a saved day works offline (videos stay online).
  MEDIA_SIGHTS.forEach(id => {
    const s = MAN.sights.find(x => x.id === id);
    const m = MEDIA[id];
    if (!s || s.day !== day || !m) return;
    m.items.forEach(it => { if (it.type === 'image' || it.type === 'audio') urls.push(mediaURL(id, it.file)); });
  });
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
    const c = await caches.open('audio-v2');
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
function queueItemsForTrack(s, t, baseIndex) {
  const more = chaptersOf(t);
  return [
    {
      file: t.file, title: displayTitle(t.title), isMore: false, baseIndex,
      num: `${baseIndex + 1}.0`,
      sight: s.name, sid: s.id, chapterCount: more.length, totalMin: trackMinutes(t)
    },
    ...more.map((c, chapterIndex) => ({
      file: c.file, title: displayTitle(c.title), isMore: true, baseIndex, chapterIndex,
      num: `${baseIndex + 1}.${chapterIndex + 1}`,
      sight: s.name, sid: s.id, parentTitle: t.title, estMin: c.est_minutes || 0
    }))
  ];
}
function sightQueue(s) { return tracksOf(s).flatMap((t, i) => queueItemsForTrack(s, t, i)); }
function dayQueue(day) {
  const items = [];
  MAN.sights.filter(s => s.day === day).forEach(s =>
    tracksOf(s).forEach((t, i) => items.push(...queueItemsForTrack(s, t, i))));
  return items;
}

// ---- render ----
function render() {
  if (screen.name === 'days') renderDays();
  else if (screen.name === 'sight') renderSight(MAN.sights.find(s => s.id === screen.id));
  else if (screen.name === 'dayplay') renderDayPlay(screen.day);
  else if (screen.name === 'monarchy') renderMonarchy();
  else if (screen.name === 'settings') renderSettings();
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
  if (queue[pos] && queue[pos].isMedia) return; // a music clip has no audience variant
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
  let h = `<div class="wrap"><div class="kickerrow"><div class="kicker">Our big trip · July 2026</div>
    <button class="gearbtn" onclick="openSettings()" aria-label="Settings">⚙︎</button></div>
    <h1 class="title serif">London → Edinburgh → York</h1>${toggleHTML()}</div>`;
  if (needsA2HS()) {
    h += `<div class="a2hs">📲 On iPhone, tap <b>Share → Add to Home Screen</b> — then the whole tour works offline.
      <button onclick="dismissA2HS()">Got it</button></div>`;
  }
  if (MON) {
    h += `<div class="crowncard" onclick="openMonarchy()">👑&nbsp; <b>The Royal Family Tree</b>
      <span>Meet the kings and queens of the trip</span></div>`;
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
      ${sights.length > 1 && DAY_MAPS.includes(day) ? `<button class="dlbtn" onclick="showMap('day-${String(day).padStart(2, '0')}', 'Day ${day} overview')">🗺</button>` : ''}
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
        <div class="meta" style="color:${a2}">${tracksOf(s).length} headings · ${expandedCount(s)} chapters · ${sightMinutes(s)} min${sightComplete(s) ? ' · ✓' : ''}</div></div>
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
  const media = MEDIA[s.id];
  if (media === undefined && MEDIA_SIGHTS.includes(s.id)) loadMedia(s.id); // re-renders when ready
  const list = tracksOf(s).map((t, i) => {
    const on = cur && cur.file === t.file;
    const more = chaptersOf(t);
    const childRows = more.map((c, j) => {
      const con = cur && cur.file === c.file;
      return `<div class="track subtrack ${con ? 'on' : ''}" onclick="playSightFile('${jsq(s.id)}','${jsq(c.file)}')">
        <div class="tnum">${con ? '▶' : (heard.has(c.file) ? '✔' : '·')}</div>
        <div style="flex:1"><h4 class="serif">${i + 1}.${j + 1} ${esc(displayTitle(c.title))}</h4>
        <div class="tm">≈ ${Math.round(c.est_minutes || 1)} min</div></div></div>`;
    }).join('');
    const relRows = (t.related || []).map(r => {
      const rs = MAN.sights.find(x => x.id === r.sight);
      if (!rs) return '';
      const when = rs.day > s.day ? `Coming up · Day ${rs.day}` : rs.day < s.day ? `Listen back · Day ${rs.day}` : 'Also today';
      return `<div class="relrow" onclick="playRelated('${jsq(r.sight)}','${jsq(r.file)}')">
        <div class="tnum">↪</div>
        <div style="flex:1"><div class="relhead"><b>${esc(displayTitle(r.title))}</b> — ${esc(rs.name)} <span class="relwhen">${when}</span></div>
        <div class="tm">${esc(r.note || '')}</div></div></div>`;
    }).join('');
    const crowns = crownsForTrack(t);
    const crownRow = crowns.length ? `<div class="crownrow">${crowns.map(m =>
      `<button onclick="event.stopPropagation();openMonarchy('${jsq(m.id)}')">👑 ${esc(m.name)}</button>`).join('')}</div>` : '';
    const mch = media ? mediaItems(s.id, i + 1) : [];
    const mediaChip = mch.length ? `<div class="mediachip" onclick="event.stopPropagation();openMedia('${jsq(s.id)}',${i + 1})">
      ${mediaChipText(mch)}<span class="mchgo">Gallery ›</span></div>` : '';
    return `<div class="track ${on ? 'on' : ''}" onclick="playSightFile('${jsq(s.id)}','${jsq(t.file)}')">
      <div class="tnum">${on ? '▶' : (heard.has(t.file) ? '✔' : `${i + 1}.0`)}</div>
      <div style="flex:1"><h4 class="serif">${i + 1}.0 ${esc(displayTitle(t.title))}</h4>
      <div class="tm">≈ ${Math.round(t.est_minutes || 1)} min${more.length ? ` · ${more.length} chapters · ${Math.round(trackMinutes(t))} min total` : ''}</div>${crownRow}${mediaChip}</div></div>${childRows}${relRows}`;
  }).join('');
  el.innerHTML = `<div class="topbar"><button class="iconbtn" onclick="goDays()">←</button>
    <div style="flex:1"><h2 class="serif" style="margin:0">${esc(s.name)}</h2>
    <div class="daylabel" style="color:${a}">Day ${s.day} · ${esc(s.date || '')}</div></div>${toggleHTML()}</div>
    <div class="hero"><img src="${imgURL(s.id, 0)}" onerror="this.style.display='none'"></div>
    <div class="maprow" onclick="showMap('${jsq(s.id)}','${jsq(s.name)}')">
      <img class="mapthumb" src="${mapURL(s.id)}" onerror="this.closest('.maprow').style.display='none'">
      <span>🗺 Map — numbered stops match the stories</span></div>
    <div class="maprow" onclick="showMap('${jsq(s.id)}-indoor','${jsq(s.name)} — inside')">
      <img class="mapthumb" src="${mapURL(s.id + '-indoor')}" onerror="this.closest('.maprow').style.display='none'">
      <span>🏛 Inside — room-by-room sketch</span></div>
    ${media ? `<div class="maprow mediarow" onclick="openMedia('${jsq(s.id)}',0)">
      <div class="mapthumb mediaicon">🖼</div>
      <span><b>Gallery</b> — ${media.counts.image} photos · ${media.counts.video} films · ${media.counts.audio} music
      <span class="mediasub">See what to look for, and hear the period music</span></span></div>` : ''}
    <div class="readlinks"><span>Read offline</span>
      <a href="${readingURL(s, 'pdf')}" download>PDF</a>
      <a href="${readingURL(s, 'epub')}" download>EPUB</a>
    </div>
    ${cur ? `<div class="nowtitle serif">${esc(cur.title)}</div>` : ''}
    <div>${list}</div>`;
}
window.playSightFile = (sid, file) => {
  const s = MAN.sights.find(x => x.id === sid);
  const items = sightQueue(s);
  const idx = Math.max(0, items.findIndex(it => it.file === file));
  loadQueue(items, idx, s.day); render();
};
// Cross-reference jump: open the related sight and play that chapter there.
window.playRelated = (sid, file) => {
  screen = { name: 'sight', id: sid };
  window.playSightFile(sid, file);
  window.scrollTo(0, 0);
};

function renderDayPlay(day) {
  const a = accent(day);
  document.documentElement.style.setProperty('--accent', a);
  const items = queue.length ? queue : dayQueue(day);
  const rows = items.map((it, i) => {
    const label = it.isMore ? '·' : (it.num || '');
    return `<div class="track ${it.isMore ? 'subtrack' : ''} ${pos === i ? 'on' : ''}" onclick="jump(${i})">
    <div class="tnum">${pos === i ? '▶' : label}</div>
    <div style="flex:1"><h4 class="serif" style="font-weight:${it.isMore ? 400 : 600}">${it.num ? `${it.num} ` : ''}${esc(it.title)}</h4>
    <div class="tm">${esc(it.sight || '')}${!it.isMore && it.chapterCount ? ` · ${it.chapterCount} chapters · ${Math.round(it.totalMin || 0)} min total` : ''}</div></div></div>`;
  }).join('');
  el.innerHTML = `<div class="topbar"><button class="iconbtn" onclick="goDays()">←</button>
    <div style="flex:1"><h2 class="serif" style="margin:0">Play the whole day</h2>
    <div class="daylabel" style="color:${a}">Day ${day} · ${cityName(day)} · ${items.length} chapters</div></div>${toggleHTML()}</div>
    <div>${rows}</div>`;
}
window.jump = i => { setPos(i); render(); };
window.openDayPlay = day => { screen = { name: 'dayplay', day }; loadQueue(dayQueue(day), 0, day); render(); };
window.openSight = id => { screen = { name: 'sight', id }; render(); };
window.goDays = () => { screen = { name: 'days' }; render(); };

// ---- settings ----
window.openSettings = () => { settingsConfirm = null; screen = { name: 'settings' }; render(); window.scrollTo(0, 0); };
window.setTheme = v => { theme = v; saveJSON('theme', v); applyTheme(); render(); };
// Swap the narration voice mid-story: same file, new voice's audio, roughly the
// same spot (voices read at slightly different pace, so "roughly" is honest).
window.setVoice = v => {
  if (!voiceAvailable(v) || v === voice) return;
  voice = v; saveJSON('voice', v);
  const it = queue[pos];
  if (it && !it.isMedia) {
    const t = au.currentTime || 0, wasPlaying = !au.paused && !au.ended;
    au.src = audioURL(it.file);
    au.playbackRate = speed;
    au.addEventListener('loadedmetadata', () => {
      if (t > 1 && au.duration && t < au.duration - 1) au.currentTime = t;
    }, { once: true });
    if (wasPlaying) au.play().catch(() => { });
  }
  render();
};
window.armConfirm = id => { settingsConfirm = id; render(); };
window.resetHeard = () => {
  heard.clear(); saveJSON('heard', []);
  try { localStorage.removeItem('resume'); } catch (_) { }
  settingsConfirm = null; render();
};

function renderSettings() {
  const seg = (on, click, label) => `<button class="${on ? 'on' : ''}" onclick="${click}">${label}</button>`;
  const voices = availableVoices();
  const voiceSec = voices.length > 1 ? `<div class="setsec"><h3>Narrator</h3>
    ${voices.map(id => `<div class="voicerow ${voice === id ? 'on' : ''}" onclick="setVoice('${id}')">
      <div class="tnum">${voice === id ? '✓' : ''}</div>
      <div style="flex:1"><b>${esc(VOICES[id].name)}</b>
      <div class="tm">${esc(VOICES[id].note)}</div></div></div>`).join('')}
    <div class="sethint">Switching mid-story keeps your place.</div></div>` : '';
  const resetBtn = settingsConfirm === 'heard'
    ? `<button class="dangerbtn armed" onclick="resetHeard()">Tap again to clear all ✓ marks</button>`
    : `<button class="dangerbtn" onclick="armConfirm('heard')">Start the tour fresh…</button>`;
  el.innerHTML = `<div class="topbar"><button class="iconbtn" onclick="goDays()">←</button>
    <div style="flex:1"><h2 class="serif" style="margin:0">Settings</h2></div></div>
    <div class="setsec"><h3>Appearance</h3>
      <div class="toggle">${seg(theme === 'auto', "setTheme('auto')", 'Auto')}${seg(theme === 'light', "setTheme('light')", '☀️ Light')}${seg(theme === 'dark', "setTheme('dark')", '🌙 Dark')}</div>
      <div class="sethint">Auto follows the phone's light/dark setting.</div></div>
    ${voiceSec}
    <div class="setsec"><h3>Story speed</h3>
      <div class="toggle">${speedList.map(v => seg(speed === v, `setSpeedPref(${v})`, `${v}×`)).join('')}</div></div>
    <div class="setsec"><h3>Progress</h3>
      <div class="sethint">${heard.size} chapter${heard.size === 1 ? '' : 's'} marked ✓ so far.</div>
      ${resetBtn}</div>`;
}

// ---- royal family tree ----
const SECTION_COLOR = { england: '--london', scotland: '--edinburgh', union: '--gold' };
function trackTitleByFile(sid, file) {
  const s = MAN.sights.find(x => x.id === sid);
  for (const a of ['kid', 'adult']) {
    const t = (s?.tracks[a] || []).find(t => t.file === file);
    if (t) return displayTitle(t.title);
  }
  return '';
}
// Monarchs whose stories touch this track (either audience's file matches).
function crownsForTrack(t) {
  if (!MON) return [];
  return MON.monarchs.filter(m => (m.links || []).some(l => l.kid === t.file || l.adult === t.file));
}
function renderMonarchy() {
  const aud = kid ? 'kid' : 'adult';
  let h = `<div class="topbar"><button class="iconbtn" onclick="goDays()">←</button>
    <div style="flex:1"><h2 class="serif" style="margin:0">👑 The Royal Family Tree</h2>
    <div class="daylabel" style="color:var(--gold)">Who's who, London to Edinburgh</div></div>${toggleHTML()}</div>
    <div class="monintro">${esc(MON.intro || '')}</div>`;
  MON.sections.forEach(sec => {
    const col = getComputedStyle(document.documentElement).getPropertyValue(SECTION_COLOR[sec.id] || '--gold').trim();
    h += `<div class="monsec"><div class="monsechead" style="color:${safeColor(col)}">${esc(sec.title)}</div>
      <div class="monsecsub">${esc(sec.sub || '')}</div>`;
    MON.monarchs.filter(m => m.section === sec.id).forEach(m => {
      const open = screen.open === m.id;
      const links = (m.links || []).filter(l => l[aud]);
      h += `<div class="mon ${open ? 'open' : ''}" id="mon-${esc(m.id)}" style="--spine:${safeColor(col)}" onclick="toggleMon('${jsq(m.id)}')">
        <div class="monface"><img src="${ASSETS}/images/monarchs/${esc(m.id)}.jpg" alt=""
          onerror="this.replaceWith(document.createTextNode('${jsq(m.emoji || '👑')}'))"></div>
        <div style="flex:1;min-width:0"><div class="monname serif">${esc(m.name)} <span class="monreign">${esc(m.reign)}</span></div>
        <div class="monhouse">${esc(m.house)}${m.rel ? ` · ${esc(m.rel)}` : ''}</div>
        ${open ? `<div class="monblurb">${esc(m.blurb || '')}</div>
        ${m.spouse ? `<div class="monfam">💍 ${esc(m.spouse)}</div>` : ''}
        ${m.children ? `<div class="monfam">👶 ${m.children.map(c => typeof c === 'string' ? esc(c)
          : `<b class="monkin" onclick="event.stopPropagation();openMonarchy('${jsq(c.id)}')">${esc(c.name)}</b>`).join(' · ')}</div>` : ''}
        ${links.map(l => {
          const rs = MAN.sights.find(x => x.id === l.sight);
          return `<div class="monlink" onclick="event.stopPropagation();playRelated('${jsq(l.sight)}','${jsq(l[aud])}')">
            ▶ <b>${esc(trackTitleByFile(l.sight, l[aud]))}</b> — ${esc(rs ? rs.name : '')} · Day ${rs ? rs.day : ''}
            <span>${esc(l.why || '')}</span></div>`;
        }).join('')}
        ${m.wiki ? `<a class="monwiki" href="https://en.wikipedia.org/wiki/${esc(encodeURIComponent(m.wiki.replace(/ /g, '_')))}"
          target="_blank" rel="noopener" onclick="event.stopPropagation()">W&nbsp; Read more on Wikipedia ↗</a>` : ''}` : ''}</div></div>`;
    });
    h += `</div>`;
  });
  h += `<div class="monfoot">${esc(MON.credits || '')}</div>`;
  el.innerHTML = h;
  if (screen.focus) {
    const card = document.getElementById(`mon-${screen.focus}`);
    if (card) card.scrollIntoView({ block: 'center' });
    screen.focus = null;
  }
}
window.toggleMon = id => { screen.open = screen.open === id ? null : id; render(); };
window.openMonarchy = id => { screen = { name: 'monarchy', open: id || null, focus: id || null }; render(); if (!id) window.scrollTo(0, 0); };

// ---- player bar ----
function paintPlayer() {
  const day = screen.day || (screen.id && MAN.sights.find(s => s.id === screen.id)?.day) || 2;
  const a = accent(day);
  const cur = queue[pos];
  document.querySelectorAll('.player').forEach(n => n.remove());
  const bar = document.createElement('div'); bar.className = 'player';
  bar.innerHTML = `<div class="inner">
    ${cur ? `<div class="ptitle serif">${cur.num ? `<span class="pnum" style="color:${a}">${esc(cur.num)}</span> ` : ''}${esc(cur.title)}
      ${cur.sight ? `<span class="psight">${esc(cur.sight)}</span>` : ''}</div>` : ''}
    <input type="range" id="scrub" min="0" max="1000" value="0" style="accent-color:${a}">
    <div class="times"><span id="tcur">0:00</span><span id="tdur"></span></div>
    <div class="notice" id="notice" style="display:${notice ? '' : 'none'}">${esc(notice)}</div>
    ${cur && cur.isMedia ? `<div class="mediaplaying">
      <span>♪ Period music${cur.sight ? ` · ${esc(cur.sight)}` : ''}</span>
      <button class="backtour" onclick="backToTour()">↩ Back to the tour</button></div>` : ''}
    ${gap && queue[pos + 1] ? `<div class="gapchip">
      <span>Next: <b>${esc(queue[pos + 1].title)}</b> in <span id="gapleft">${gapLeft()}</span>s</span>
      <button class="gapstay" onclick="stayHere()">✕ stay</button></div>` : ''}
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
