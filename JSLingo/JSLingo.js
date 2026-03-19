(() => {
  if (window.__jslingo_running) {
    console.log('[JSLingo] Already running');
    return;
  }
  window.__jslingo_running = true;

  const VERSION = '1.0.0';

  // ── Helpers ──────────────────────────────────────────────────────
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  const getCookie = name => {
    const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : null;
  };

  const getJwt = () => getCookie('jwt_token');

  const decodeJwt = token => {
    try {
      const b64 = token.split('.')[1].replace(/-/g,'+').replace(/_/g,'/');
      return JSON.parse(decodeURIComponent(atob(b64).split('').map(c =>
        '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)).join('')));
    } catch { return null; }
  };

  const headers = jwt => ({
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + jwt,
  });

  // ── State ─────────────────────────────────────────────────────────
  const state = {
    running:  false,
    jwt:      null,
    sub:      null,
    userInfo: null,
    log:      [],
  };

  // ── UI ────────────────────────────────────────────────────────────
  const UI_ID = '_jslingo_ui';

  const addLog = (msg, type = 'info') => {
    const colors = { info: '#888', success: '#6aaf7a', error: '#b05c5c', farm: '#d4a96a' };
    const ts = new Date().toLocaleTimeString('en-GB');
    state.log.push({ ts, msg, type });
    const el = document.getElementById(UI_ID + '_log');
    if (!el) return;
    const line = document.createElement('div');
    line.style.cssText = `color:${colors[type]||'#888'};margin:2px 0;`;
    line.textContent = `${ts}  ${msg}`;
    el.appendChild(line);
    el.scrollTop = el.scrollHeight;
  };

  const buildUI = () => {
    if (document.getElementById(UI_ID)) return;
    const wrap = document.createElement('div');
    wrap.id = UI_ID;
    wrap.style.cssText = `
      position:fixed; bottom:20px; right:20px; z-index:999999;
      width:380px; background:#0e0e0e; border:1px solid #2a2a2a;
      border-radius:6px; font-family:'JetBrains Mono',monospace;
      font-size:12px; color:#c8c0b0; box-shadow:0 8px 32px rgba(0,0,0,0.6);
      user-select:none;
    `;

    wrap.innerHTML = `
      <div id="${UI_ID}_bar" style="padding:10px 14px;border-bottom:1px solid #1e1e1e;
           display:flex;align-items:center;justify-content:space-between;cursor:move;">
        <span style="color:#d4a96a;font-weight:700;letter-spacing:1px;">
          JS<span style="color:#6aaf7a">LINGO</span>
          <span style="color:#555;font-weight:400;font-size:11px;">v${VERSION}</span>
        </span>
        <div style="display:flex;gap:8px;align-items:center;">
          <span id="${UI_ID}_user" style="color:#555;font-size:11px;"></span>
          <button id="${UI_ID}_close" style="background:none;border:none;color:#555;
            cursor:pointer;font-size:14px;padding:0 2px;">×</button>
        </div>
      </div>

      <div style="padding:12px 14px;border-bottom:1px solid #1e1e1e;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
          <button class="_jsl_btn" data-action="xp"     style="color:#d4a96a;">⬡ XP Farm</button>
          <button class="_jsl_btn" data-action="gems"   style="color:#6aa0af;">◈ Gem Farm</button>
          <button class="_jsl_btn" data-action="streak" style="color:#af9a6a;">⟳ Streak</button>
          <button class="_jsl_btn" data-action="quest"  style="color:#6aaf7a;">✓ Daily Quest</button>
        </div>
        <div style="margin-top:8px;display:flex;align-items:center;gap:8px;">
          <span style="color:#555;font-size:11px;">delay ms</span>
          <input id="${UI_ID}_delay" type="number" value="1500" min="200" step="100"
            style="width:70px;background:#141414;border:1px solid #2a2a2a;color:#c8c0b0;
            border-radius:3px;padding:3px 6px;font-family:inherit;font-size:11px;">
          <button id="${UI_ID}_stop" style="margin-left:auto;background:none;
            border:1px solid #3a2020;border-radius:3px;color:#b05c5c;
            font-family:inherit;font-size:11px;padding:3px 10px;cursor:pointer;">
            ■ Stop
          </button>
        </div>
      </div>

      <div id="${UI_ID}_log" style="height:160px;overflow-y:auto;padding:10px 14px;
           line-height:1.6;font-size:11px;"></div>
    `;

    // Button styles
    wrap.querySelectorAll('._jsl_btn').forEach(b => {
      b.style.cssText += `
        background:#141414;border:1px solid #2a2a2a;border-radius:3px;
        padding:7px 10px;cursor:pointer;font-family:inherit;font-size:12px;
        text-align:left;transition:border-color 0.15s;
      `;
      b.addEventListener('mouseenter', () => b.style.borderColor = '#444');
      b.addEventListener('mouseleave', () => b.style.borderColor = '#2a2a2a');
      b.addEventListener('click', () => startFarm(b.dataset.action));
    });

    document.getElementById(UI_ID + '_stop').addEventListener('click', stopFarm);
    document.getElementById(UI_ID + '_close').addEventListener('click', () => {
      stopFarm();
      wrap.remove();
      window.__jslingo_running = false;
    });

    // Draggable
    let dx = 0, dy = 0, dragging = false;
    const bar = document.getElementById(UI_ID + '_bar');
    bar.addEventListener('mousedown', e => {
      dragging = true;
      dx = e.clientX - wrap.getBoundingClientRect().left;
      dy = e.clientY - wrap.getBoundingClientRect().top;
    });
    document.addEventListener('mousemove', e => {
      if (!dragging) return;
      wrap.style.left  = (e.clientX - dx) + 'px';
      wrap.style.right = 'auto';
      wrap.style.top   = (e.clientY - dy) + 'px';
      wrap.style.bottom = 'auto';
    });
    document.addEventListener('mouseup', () => dragging = false);

    document.body.appendChild(wrap);
  };

  // ── Init ──────────────────────────────────────────────────────────
  const init = async () => {
    state.jwt = getJwt();
    if (!state.jwt) {
      addLog('No JWT token found — log in to Duolingo first', 'error');
      return false;
    }
    const decoded = decodeJwt(state.jwt);
    state.sub = decoded?.sub;
    if (!state.sub) {
      addLog('Cannot decode JWT', 'error');
      return false;
    }
    try {
      const res  = await fetch(
        `https://www.duolingo.com/2017-06-30/users/${state.sub}?fields=id,username,streak,totalXp,gems,fromLanguage,learningLanguage`,
        { headers: headers(state.jwt) }
      );
      state.userInfo = await res.json();
      const u = state.userInfo;
      document.getElementById(UI_ID + '_user').textContent =
        `${u.username}  str:${u.streak}  xp:${u.totalXp}`;
      addLog(`Logged in as ${u.username}`, 'success');
      return true;
    } catch (e) {
      addLog('Failed to fetch user info: ' + e.message, 'error');
      return false;
    }
  };

  // ── Farm functions ────────────────────────────────────────────────
  const getDelay = () =>
    parseInt(document.getElementById(UI_ID + '_delay')?.value || '1500');

  const stopFarm = () => {
    state.running = false;
    addLog('Stopped.', 'info');
  };

  const startFarm = async action => {
    if (state.running) { addLog('Already running — stop first', 'error'); return; }
    const ok = await init();
    if (!ok) return;
    state.running = true;
    const delay = getDelay();
    addLog(`Starting ${action} farm · delay ${delay}ms`, 'info');
    try {
      if (action === 'xp')     await farmXP(delay);
      if (action === 'gems')   await farmGems(delay);
      if (action === 'streak') await farmStreak(delay);
      if (action === 'quest')  await farmQuest();
    } catch (e) {
      addLog('Error: ' + e.message, 'error');
    }
    state.running = false;
  };

  // XP
  const farmXP = async delay => {
    let total = 0;
    while (state.running) {
      try {
        const now = Date.now() / 1000;
        const body = {
          awardXp: true, completedBonusChallenge: true,
          fromLanguage: state.userInfo.fromLanguage || 'en',
          learningLanguage: state.userInfo.learningLanguage || 'fr',
          hasXpBoost: false, illustrationFormat: 'svg',
          isFeaturedStoryInPracticeHub: true, isLegendaryMode: true,
          isV2Redo: false, isV2Story: false, masterVersion: true,
          maxScore: 0, score: 0, happyHourBonusXp: 469,
          startTime: now, endTime: now + 1,
        };
        const res = await fetch(
          'https://stories.duolingo.com/api2/stories/fr-en-le-passeport/complete',
          { method: 'POST', headers: headers(state.jwt), body: JSON.stringify(body) }
        );
        if (res.status === 200) {
          const data = await res.json();
          const xp = data.awardedXp || 0;
          total += xp;
          addLog(`+${xp} XP  total=${total.toLocaleString()}`, 'farm');
        } else if (res.status === 429) {
          addLog('Rate limited — waiting 5s', 'info');
          await sleep(5000);
          continue;
        } else {
          addLog(`XP request failed (${res.status})`, 'error');
        }
      } catch (e) { addLog('XP error: ' + e.message, 'error'); }
      await sleep(delay);
    }
  };

  // Gems
  const farmGems = async delay => {
    const u = state.userInfo;
    let total = 0;
    const rewardId = 'SKILL_COMPLETION_BALANCED-dd2495f4_d44e_3fc3_8ac8_94e2191506f0-2-GEMS';
    while (state.running) {
      try {
        const res = await fetch(
          `https://www.duolingo.com/2017-06-30/users/${state.sub}/rewards/${rewardId}`,
          {
            method: 'PATCH',
            headers: headers(state.jwt),
            body: JSON.stringify({ consumed: true,
              fromLanguage: u.fromLanguage, learningLanguage: u.learningLanguage }),
          }
        );
        if (res.status === 200) {
          total += 30;
          addLog(`+30 gems  total=${total.toLocaleString()}`, 'farm');
        } else if (res.status === 403) {
          addLog('Rate limited (403) — stopping', 'error');
          break;
        } else {
          addLog(`Gems request failed (${res.status})`, 'error');
        }
      } catch (e) { addLog('Gems error: ' + e.message, 'error'); }
      await sleep(delay);
    }
  };

  // Streak (1 session)
  const farmStreak = async delay => {
    const u = state.userInfo;
    let count = 0;
    while (state.running) {
      try {
        const sessionPayload = {
          challengeTypes: ['translate','assist','match','tapComplete'],
          fromLanguage: u.fromLanguage || 'en',
          isFinalLevel: false, isV2: true, juicy: true,
          learningLanguage: u.learningLanguage || 'fr',
          smartTipsVersion: 2, type: 'GLOBAL_PRACTICE',
        };
        const s1 = await fetch('https://www.duolingo.com/2017-06-30/sessions',
          { method: 'POST', headers: headers(state.jwt),
            body: JSON.stringify(sessionPayload) });
        if (s1.status !== 200) { addLog(`Session create failed (${s1.status})`, 'error'); break; }
        const sess = await s1.json();
        const now = Math.floor(Date.now() / 1000);
        const s2 = await fetch(
          `https://www.duolingo.com/2017-06-30/sessions/${sess.id}`,
          { method: 'PUT', headers: headers(state.jwt),
            body: JSON.stringify({ ...sess, heartsLeft: 5,
              startTime: now - 60, endTime: now,
              enableBonusPoints: false, failed: false,
              maxInLessonStreak: 9, shouldLearnThings: true }) }
        );
        if (s2.status === 200) {
          count++;
          addLog(`Streak session ${count} complete`, 'farm');
        } else {
          addLog(`Session update failed (${s2.status})`, 'error');
        }
      } catch (e) { addLog('Streak error: ' + e.message, 'error'); }
      await sleep(delay);
    }
  };

  // Daily Quest
  const farmQuest = async () => {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    try {
      const prog = await fetch(
        `https://goals-api.duolingo.com/users/${state.sub}/progress?timezone=${tz}&ui_language=en`,
        { headers: headers(state.jwt) }
      );
      const data = await prog.json();
      const metrics = (data.metrics || [])
        .filter(m => m.value < m.threshold)
        .map(m => m.metricType);
      if (!metrics.length) { addLog('All quests already complete!', 'success'); return; }
      addLog(`Found ${metrics.length} quest(s): ${metrics.join(', ')}`, 'info');
      const res = await fetch(
        `https://goals-api.duolingo.com/users/${state.sub}/progress/batch`,
        { method: 'POST', headers: headers(state.jwt),
          body: JSON.stringify({ updates: metrics.map(m => ({
            metricType: m, incrementValue: 9999, timezone: tz })) }) }
      );
      if (res.status === 200) addLog('All quests completed!', 'success');
      else addLog(`Quest batch failed (${res.status})`, 'error');
    } catch (e) { addLog('Quest error: ' + e.message, 'error'); }
  };

  // ── Start ─────────────────────────────────────────────────────────
  buildUI();
  addLog(`JSLingo v${VERSION} loaded`, 'success');
})();
