'use strict';

const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));
const pct = v => Math.round(v * 100) + '%';
const band = v => v >= 0.75 ? 'ok' : v >= 0.4 ? 'warn' : 'crit';

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => null);
  if (!r.ok) throw new Error(body && body.detail ? JSON.stringify(body.detail) : 'HTTP ' + r.status);
  return body;
}
const working = (el, msg) => { el.innerHTML = `<span class="working"><span class="spin"></span> ${esc(msg)}</span>`; };
const failed  = (el, e)   => { el.innerHTML = `<span class="chip crit">failed</span><pre>${esc(e.message)}</pre>`; };
const said    = (el, msg, kind = 'ok') => { el.innerHTML = `<span class="chip ${kind}">${esc(msg)}</span>`; };

function table(rows, cols) {
  if (!rows.length) return '<div class="empty">Nothing here yet.</div>';
  const head = cols.map(c => `<th${c.right ? ' style="text-align:right"' : ''}>${esc(c.h)}</th>`).join('');
  const body = rows.map(r => '<tr>' + cols.map(c => `<td${c.cls ? ' class="' + c.cls + '"' : ''}>${c.f(r)}</td>`).join('') + '</tr>').join('');
  return `<div class="table-scroll"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}
const meter = v => `<span class="meter"><span class="meter-track"><i class="meter-fill ${band(v)}" style="width:${Math.min(Math.max(v,0),1)*100}%"></i></span><span class="num">${pct(v)}</span></span>`;
const figures = items => `<div class="figures">${items.map(i =>
  `<div class="figure ${i.kind || ''}"><div class="figure-v">${esc(i.v)}</div><div class="figure-l">${esc(i.l)}</div></div>`).join('')}</div>`;

function fillSelect(sel, items, label) {
  const prev = sel.value;
  sel.innerHTML = items.map(i => `<option value="${i.id}">${esc(label(i))}</option>`).join('');
  if (prev && items.some(i => String(i.id) === prev)) sel.value = prev;
}

const S = {
  get plan() { try { return localStorage.getItem('cos.plan'); } catch { return null; } },
  set plan(v) { try { localStorage.setItem('cos.plan', v); } catch {} },
  get question() { try { return localStorage.getItem('cos.q'); } catch { return null; } },
  set question(v) { try { localStorage.setItem('cos.q', v); } catch {} },
};

async function teacherIdentity() {
  const response = await api('/classroom/me');
  if (response.role !== 'teacher') throw new Error('Sign in through the teacher portal first.');
  return response.id;
}

/* ---------- theme ---------- */
(function theme() {
  let saved = null;
  try { saved = localStorage.getItem('studio-theme') || localStorage.getItem('cos.theme'); } catch {}
  document.documentElement.setAttribute('data-theme', saved || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark':'light'));
  $('theme-toggle').onclick = () => {
    const dark = matchMedia('(prefers-color-scheme: dark)').matches;
    const now = document.documentElement.getAttribute('data-theme') || (dark ? 'dark' : 'light');
    const next = now === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('cos.theme', next); localStorage.setItem('studio-theme', next); } catch {}
  };
})();

/* ---------- navigation ---------- */
document.querySelectorAll('#spine button').forEach(b => { b.onclick = () => show(b.dataset.stage); });
document.querySelectorAll('[data-refresh]').forEach(b => { b.onclick = () => window[b.dataset.refresh](); });

function show(name) {
  if (!$('stage-' + name)) name = 'upload';
  document.querySelectorAll('.stage').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('#spine button').forEach(b => b.classList.toggle('active', b.dataset.stage === name));
  $('stage-' + name).classList.add('active');
  document.querySelectorAll('#spine button').forEach(button=>{
    if(button.dataset.stage===name) button.setAttribute('aria-current','step');
    else button.removeAttribute('aria-current');
  });
  window.scrollTo({top:0,behavior:'instant'});
  history.replaceState(null, '', '#' + name);
  (ON_ENTER[name] || (() => {}))();
}

/* ---------- masthead ---------- */
async function health() {
  for (const [path, dot, chip] of [['/health', 'dot-api', 'chip-api'], ['/health/db', 'dot-db', 'chip-db']]) {
    let ok = false;
    try { ok = (await fetch(path)).ok; } catch {}
    $(dot).className = 'dot ' + (ok ? 'ok' : 'crit');
    $(chip).className = 'chip ' + (ok ? 'ok' : 'crit');
  }
}

/** The eight quantities that flow through the pipeline, read as one row so
 *  a stalled stage shows up as a zero beside a populated neighbour. One
 *  request, not one per question. */
const LEDGER = ['documents', 'spans', 'objectives', 'questions', 'mappings', 'units', 'scheduled', 'claims'];
async function ledger() {
  let s;
  try { s = await api('/stats'); } catch { return; }
  $('ledger').innerHTML = LEDGER.map(k =>
    `<div class="ledger-cell"><div class="ledger-figure${s[k] ? '' : ' zero'}">${s[k]}</div>` +
    `<div class="ledger-label">${k}</div></div>`).join('');
}

/* ---------- 01 documents ---------- */
let DOCS = [];
async function loadDocuments() {
  const el = $('out-docs');
  try {
    DOCS = await api('/documents');
    el.innerHTML = table(DOCS, [
      { h: 'Title', f: d => esc(d.title) },
      { h: 'Type', f: d => `<span class="chip info">${esc(d.doc_type)}</span>` },
      { h: 'Parser', f: d => `<span class="mono">${esc(d.parser_used || '—')}</span>` },
      { h: 'Spans', right: true, cls: 'num-col', f: d => d.span_count },
    ]);
    const label = d => `${d.title} · ${d.doc_type}`;
    fillSelect($('cur-doc'), DOCS, label);
    fillSelect($('q-doc'), DOCS.filter(d => d.doc_type === 'past_paper'), label);
    $('q-ms').innerHTML = '<option value="">none</option>' +
      DOCS.filter(d => d.doc_type === 'mark_scheme').map(d => `<option value="${d.id}">${esc(label(d))}</option>`).join('');
  } catch (e) { failed(el, e); }
}

$('btn-upload').onclick = async () => {
  const el = $('out-upload'), f = $('up-file').files[0];
  if (!f) return said(el, 'Choose a file first', 'warn');
  working(el, 'Parsing — a scanned PDF goes page by page through OCR and can take a while');
  const fd = new FormData();
  fd.append('title', $('up-title').value || f.name);
  fd.append('doc_type', $('up-type').value);
  fd.append('file', f);
  try {
    const d = await api('/ingestion/documents', { method: 'POST', body: fd });
    el.innerHTML = figures([
      { v: d.span_count, l: 'spans stored', kind: 'ok' },
      { v: d.parser_confidence == null ? '—' : pct(d.parser_confidence), l: 'parser confidence' },
      { v: d.parser_used || '—', l: 'parser reached' },
    ]);
    await loadDocuments(); ledger();
  } catch (e) { failed(el, e); }
};

/* ---------- 02 curriculum ---------- */
let NODES = [];
async function loadNodes() {
  const el = $('out-nodes');
  try {
    NODES = await api('/curriculum-nodes');
    const edges = await api('/curriculum-edges');
    const prereq = edges.filter(e => e.edge_type === 'prerequisite').length;
    el.innerHTML = figures([
      { v: NODES.length, l: 'nodes' },
      { v: edges.length, l: 'edges' },
      { v: prereq, l: 'prerequisites' },
    ]) + table(NODES, [
      { h: 'Ref', cls: 'mono', f: n => esc(n.syllabus_ref || '—') },
      { h: 'Kind', f: n => `<span class="chip">${esc(n.node_type)}</span>` },
      { h: 'Label', f: n => esc(n.label) },
      { h: 'Origin', f: n => `<span class="chip ${n.origin === 'official' ? 'ok' : ''}">${esc(n.origin)}</span>` },
      { h: 'Confidence', f: n => meter(n.confidence) },
    ]);
    fillSelect($('gen-node'), NODES, n => `${n.syllabus_ref || ''} ${n.label}`.trim());
  } catch (e) { failed(el, e); }
}

$('btn-extract').onclick = async () => {
  const el = $('out-extract'), id = $('cur-doc').value;
  if (!id) return said(el, 'Upload a syllabus first', 'warn');
  working(el, 'Reading the syllabus and proposing a structure');
  try {
    const nodes = await api(`/ingestion/documents/${id}/curriculum`, { method: 'POST' });
    el.innerHTML = `<span class="chip ok">${nodes.length} nodes extracted</span> <span class="working"><span class="spin"></span> embedding for retrieval</span>`;
    let embedded = 0, warn = '';
    try { embedded = (await api('/ingestion/curriculum/embeddings', { method: 'POST' })).nodes_embedded; }
    catch { warn = ' <span class="chip warn">embedding unavailable — mapping will need explicit candidates</span>'; }
    el.innerHTML = `<span class="chip ok">${nodes.length} nodes extracted</span> ` +
      (embedded ? `<span class="chip ok">${embedded} embedded</span>` : '') + warn;
    await loadNodes(); ledger();
  } catch (e) { failed(el, e); }
};

/* ---------- 03 questions ---------- */
let QUESTIONS = [];
async function loadQuestions() {
  const el = $('out-questions');
  try {
    QUESTIONS = await api('/questions');
    el.innerHTML = table(QUESTIONS, [
      { h: 'Reference', cls: 'mono', f: q => esc(q.question_ref) },
      { h: 'Question', f: q => esc(q.text.slice(0, 150)) },
      { h: 'Marks', right: true, cls: 'num-col', f: q => q.marks ?? '—' },
    ]);
    fillSelect($('map-q'), QUESTIONS, q => `${q.question_ref} — ${q.text.slice(0, 64)}`);
    if (S.question && QUESTIONS.some(q => q.id === S.question)) $('map-q').value = S.question;
  } catch (e) { failed(el, e); }
}

$('btn-questions').onclick = async () => {
  const el = $('out-qparse'), id = $('q-doc').value;
  if (!id) return said(el, 'Upload a past paper first', 'warn');
  working(el, 'Parsing questions');
  try {
    const r = await api(`/ingestion/documents/${id}/questions`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mark_scheme_document_id: $('q-ms').value || null,
        year: $('q-year').value ? +$('q-year').value : null,
        paper_ref: $('q-ref').value || null,
      }),
    });
    el.innerHTML = figures([
      { v: r.questions_created, l: 'questions', kind: 'ok' },
      { v: r.mark_scheme_entries_created, l: 'scheme entries', kind: 'ok' },
      { v: r.questions_without_mark_scheme.length, l: 'unmatched questions', kind: r.questions_without_mark_scheme.length ? 'warn' : '' },
      { v: r.mark_scheme_entries_without_question.length, l: 'orphan entries', kind: r.mark_scheme_entries_without_question.length ? 'warn' : '' },
    ]) + `<p class="aside">The unmatched counts are the parser being honest, not the parser failing quietly.</p>`;
    await loadQuestions(); ledger();
  } catch (e) { failed(el, e); }
};

/* ---------- 04 mapping ---------- */
const mappingRows = ms => table(ms, [
  { h: 'Objective', f: m => esc(m.node_label) },
  { h: 'Weight', f: m => meter(m.weight) },
  { h: 'Confidence', f: m => meter(m.confidence) },
  { h: 'Method', f: m => `<span class="chip ${m.mapping_method === 'human_corrected' ? 'ok' : ''}">${esc(m.mapping_method)}</span>` },
]);

async function loadMappings() {
  const el = $('out-mappings'), qid = $('map-q').value;
  if (!qid) return void (el.innerHTML = '<div class="empty">No question selected.</div>');
  try { el.innerHTML = mappingRows(await api(`/questions/${qid}/mappings`)); }
  catch (e) { failed(el, e); }
}
$('map-q').onchange = () => { S.question = $('map-q').value; loadMappings(); };

$('btn-map').onclick = async () => {
  const el = $('out-map'), qid = $('map-q').value;
  if (!qid) return said(el, 'Parse some questions first', 'warn');
  S.question = qid;
  working(el, 'Running the ensemble — embedding, lexical, terminology, model');
  try {
    const ms = await api(`/mappings/questions/${qid}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ min_confidence: +$('map-conf').value }),
    });
    el.innerHTML = ms.length
      ? `<span class="chip ok">${ms.length} objective${ms.length === 1 ? '' : 's'} above the floor</span>` +
        mappingRows(ms.map(m => ({ ...m, node_label: (NODES.find(n => n.id === m.node_id) || {}).label || m.node_id })))
      : `<span class="chip warn">nothing above the confidence floor</span>
         <p class="aside">Lower the floor to trade precision for recall, or check the objective actually exists.</p>`;
    await loadMappings(); ledger();
  } catch (e) { failed(el, e); }
};

/* ---------- 05 corrections ---------- */
async function loadCorrectable() {
  const el = $('out-correctable'), qid = S.question || $('map-q').value;
  if (!qid) return void (el.innerHTML = '<div class="empty">Pick a question in stage 04 first.</div>');
  try {
    const ms = await api(`/questions/${qid}/mappings`);
    if (!ms.length) return void (el.innerHTML = '<div class="empty">That question has no mappings yet.</div>');
    el.innerHTML = table(ms, [
      { h: 'Objective', f: m => esc(m.node_label) },
      { h: 'Current', f: m => meter(m.weight) },
      { h: 'Method', f: m => `<span class="chip ${m.mapping_method === 'human_corrected' ? 'ok' : ''}">${esc(m.mapping_method)}</span>` },
      { h: 'Corrected weight', f: m => `<input style="width:5.5rem" type="number" step="0.05" min="0" max="1" value="${m.weight.toFixed(2)}" id="cw-${m.id}">` },
      { h: '', f: m => `<button class="quiet" onclick="correct('${m.id}',${m.weight})">Save</button>` },
    ]);
  } catch (e) { failed(el, e); }
}

async function correct(id, before) {
  const el = $('out-correctable'), after = +$('cw-' + id).value;
  try {
    const teacherId = await teacherIdentity();
    await api('/corrections/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        entity_type: 'question_node_mapping', entity_id: id,
        before_value: { weight: before }, after_value: { weight: after }, teacher_id: teacherId,
      }),
    });
    await loadCorrectable();
    el.insertAdjacentHTML('afterbegin',
      '<p style="margin:0 0 .7rem"><span class="chip ok">correction recorded</span> ' +
      '<span class="chip ok">confidence now certain</span> <span class="chip ok">method now human_corrected</span></p>');
  } catch (e) { failed(el, e); }
}

/* ---------- 05b mastery ---------- */
const MASTERY_STATUS = { mastered: 'ok', needs_reinforcement: 'warn', reteach: 'crit' };

async function loadMastery() {
  const el = $('out-mastery'), classId = $('mast-class').value;
  if (!classId) return;
  try {
    const rows = await api(`/mastery/?class_id=${encodeURIComponent(classId)}`);
    if (!rows.length) {
      el.innerHTML = '<div class="empty">No mastery signals yet. Mark objectives below.</div>';
      // still load summary
      loadMasterySummary();
      return;
    }
    el.innerHTML = table(rows, [
      { h: 'Objective', f: r => esc(r.node_label) },
      { h: 'Status', f: r => `<span class="chip ${MASTERY_STATUS[r.status] || ''}">${esc(r.status)}</span>` },
      { h: 'Marked by', f: r => esc(r.marked_by) },
      { h: '', f: r => {
        const opts = ['mastered','needs_reinforcement','reteach']
          .map(s => `<option value="${s}"${s === r.status ? ' selected' : ''}>${s}</option>`).join('');
        return `<select id="ms-${r.id}" style="width:auto;font-size:.78rem">${opts}</select> <button class="quiet" onclick="updateMastery('${r.id}','${esc(r.node_id)}')">Save</button>`;
      }},
    ]);
    loadMasterySummary();
  } catch (e) { failed(el, e); }
}

async function updateMastery(signalId, nodeId) {
  const el = $('out-mastery'), classId = $('mast-class').value;
  const status = $('ms-' + signalId).value;
  try {
    const teacherId = await teacherIdentity();
    await api('/mastery/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ class_id: classId, node_id: nodeId, status, teacher_id: teacherId }),
    });
    await loadMastery();
  } catch (e) { failed(el, e); }
}

async function loadMasterySummary() {
  const el = $('out-mastery-summary'), classId = $('mast-class').value;
  if (!classId) return;
  try {
    const s = await api(`/mastery/summary?class_id=${encodeURIComponent(classId)}`);
    el.innerHTML = figures([
      { v: s.mastered, l: 'mastered', kind: 'ok' },
      { v: s.needs_reinforcement, l: 'reinforce', kind: 'warn' },
      { v: s.reteach, l: 'reteach', kind: 'crit' },
      { v: s.unmarked, l: 'unmarked' },
    ]);
  } catch {}
}

$('btn-mastery').onclick = async () => {
  const el = $('out-mastery'), classId = $('mast-class').value, nodeId = $('mast-node').value;
  if (!classId || !nodeId) return said(el, 'Choose a class and objective', 'warn');
  try {
    const teacherId = await teacherIdentity();
    await api('/mastery/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ class_id: classId, node_id: nodeId, status: $('mast-status').value, teacher_id: teacherId }),
    });
    await loadMastery();
  } catch (e) { failed(el, e); }
};

/* ---------- 06 emphasis ---------- */
let EMPHASIS = {};
$('btn-emphasis').onclick = async () => {
  const el = $('out-emphasis');
  working(el, 'Scoring');
  try {
    const y = $('emph-year').value;
    const rows = await api('/emphasis/' + (y ? `?current_year=${y}` : ''));
    if (!rows.length) return void (el.innerHTML =
      '<div class="empty">No mapped questions yet — emphasis is computed from stage 04.</div>');
    rows.sort((a, b) => b.score - a.score);
    const label = Object.fromEntries(NODES.map(n => [n.id, n.label]));
    EMPHASIS = Object.fromEntries(rows.map(r => [r.node_id, r.score]));
    el.innerHTML = table(rows, [
      { h: 'Objective', f: r => esc(label[r.node_id] || r.node_id) },
      { h: 'Emphasis', f: r => meter(r.score) },
      { h: 'Freq', right: true, cls: 'num-col', f: r => r.frequency.toFixed(2) },
      { h: 'Recency', right: true, cls: 'num-col', f: r => r.recency.toFixed(2) },
      { h: 'Marks', right: true, cls: 'num-col', f: r => r.marks.toFixed(2) },
      { h: 'Spec', right: true, cls: 'num-col', f: r => r.syllabus.toFixed(2) },
      { h: 'Struct', right: true, cls: 'num-col', f: r => r.structural.toFixed(2) },
    ]) + '<p class="aside">All five components are normalised to a common scale, so the weights mean what they say.</p>';
  } catch (e) { failed(el, e); }
};

/* ---------- 07 calendar ---------- */
async function loadCalendars() {
  try {
    const cals = await api('/calendars/');
    const label = c => `${c.school_id} · ${c.term_start} → ${c.term_end}`;
    ['win-cal', 'plan-cal', 'dis-cal'].forEach(id => fillSelect($(id), cals, label));
  } catch {}
}
$('btn-calendar').onclick = async () => {
  const el = $('out-calendar');
  if (!$('cal-start').value || !$('cal-end').value) return said(el, 'Set the term start and end', 'warn');
  working(el, 'Modelling the term');
  try {
    const c = await api('/calendars/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        school_id: $('cal-school').value, term_start: $('cal-start').value, term_end: $('cal-end').value,
        non_teaching_dates: $('cal-off').value.split(',').map(s => s.trim()).filter(Boolean),
      }),
    });
    el.innerHTML = figures([{ v: c.day_count, l: 'days modelled', kind: 'ok' }]);
    await loadCalendars();
  } catch (e) { failed(el, e); }
};
$('btn-windows').onclick = async () => {
  const el = $('out-windows'), cal = $('win-cal').value;
  if (!cal) return said(el, 'Create a calendar first', 'warn');
  working(el, 'Expanding the slot across the term');
  try {
    const r = await api(`/calendars/${cal}/instruction-windows`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slots: [{
        subject: $('win-subject').value, class_id: $('win-class').value,
        weekday: +$('win-day').value, start_time: $('win-start').value, end_time: $('win-end').value }] }),
    });
    el.innerHTML = figures([{ v: r.windows_created, l: 'teaching windows', kind: 'ok' }]);
  } catch (e) { failed(el, e); }
};

/* ---------- 08 plan ---------- */
$('btn-units').onclick = async () => {
  const el = $('out-units');
  const objectives = NODES.filter(n => n.node_type === 'objective');
  const targets = objectives.length ? objectives : NODES;
  if (!targets.length) return said(el, 'Extract a curriculum first', 'warn');
  working(el, 'Creating teaching units');
  try {
    const made = await api('/ingestion/teaching-units', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        node_ids: targets.map(n => n.id), default_duration_minutes: +$('tu-dur').value, priorities: EMPHASIS,
      }),
    });
    const all = await api('/teaching-units');
    el.innerHTML = `<span class="chip ok">${made.length} new</span> <span class="chip">${all.length} total</span>` +
      table(all, [
        { h: 'Objective', f: u => esc(u.node_label) },
        { h: 'Minutes', right: true, cls: 'num-col', f: u => u.duration_minutes },
        { h: 'Priority', f: u => meter(Math.min(u.priority, 1)) },
      ]);
    ledger();
  } catch (e) { failed(el, e); }
};

$('btn-plan').onclick = async () => {
  const el = $('out-plan'), cal = $('plan-cal').value;
  if (!cal) return said(el, 'Create a calendar first', 'warn');
  working(el, 'Solving — CP-SAT');
  try {
    const units = await api('/teaching-units');
    const plan = await api('/planning/plans', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        calendar_id: cal, subject: $('plan-subject').value, class_id: $('plan-class').value,
        node_ids: units.map(u => u.node_id), trigger_reason: 'initial_plan',
      }),
    });
    S.plan = plan.plan_version_id;
    const unsched = plan.unscheduled_unit_ids.length;
    el.innerHTML = figures([
      { v: plan.assignments.length, l: 'lessons placed', kind: 'ok' },
      { v: unsched, l: 'unscheduled', kind: unsched ? 'warn' : 'ok' },
      { v: plan.status, l: 'solver status' },
    ]);
    await schedule(el, plan.plan_version_id); ledger();
  } catch (e) { failed(el, e); }
};

async function schedule(el, planId, justTarget) {
  const jTarget = justTarget || 'out-justification';
  try {
    const rows = await api(`/planning/plans/${planId}`);
    if (el) el.insertAdjacentHTML('beforeend', table(rows, [
      { h: 'Date', cls: 'mono', f: r => r.date },
      { h: 'Lesson', f: r => esc(r.node_label) },
      { h: 'Minutes', right: true, cls: 'num-col', f: r => r.scheduled_minutes },
      { h: 'Status', f: r => `<span class="chip">${esc(r.status)}</span>` },
      { h: '', f: r => `<button class="quiet" onclick="showJustification('${planId}','${r.id}','${jTarget}')" style="font-size:.72rem">why?</button>` },
    ]));
    fillSelect($('gen-unit'), rows, r => `${r.date} — ${r.node_label}`);
  } catch {}
}

async function showJustification(planId, unitId, targetId) {
  const el = $(targetId || 'out-justification');
  if (!el) return;
  working(el, 'Loading justification');
  try {
    const j = await api(`/planning/plans/${planId}/units/${unitId}/justification`);
    let html = `<div class="panel" style="margin-top:.8rem"><div class="panel-head"><h3>${esc(j.node_label)}</h3>`;
    if (j.syllabus_ref) html += ` <span class="chip info">${esc(j.syllabus_ref)}</span>`;
    if (j.was_moved) html += ` <span class="chip warn">moved from ${esc(String(j.previous_date))}</span>`;
    html += `</div><div class="panel-body">`;
    if (j.node_description) html += `<p style="margin:0 0 .8rem;color:var(--ink-soft)">${esc(j.node_description)}</p>`;
    // Time context
    if (j.days_to_term_end != null) {
      html += `<div style="margin-bottom:.8rem"><span class="chip info">${j.days_to_term_end} days to term end</span> `;
      html += `<span class="chip">${j.scheduled_minutes} min on ${j.date}</span></div>`;
    }
    // Prerequisites
    if (j.prerequisites.length) {
      html += `<div style="margin-bottom:.8rem"><span style="font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-faint)">Prerequisites</span><ul style="margin:.3rem 0 0;padding-left:1.2rem">`;
      j.prerequisites.forEach(p => { html += `<li>${esc(p.node_label)}</li>`; });
      html += `</ul></div>`;
    }
    // Emphasis
    if (j.emphasis_score != null) {
      html += `<div style="margin-bottom:.8rem"><span style="font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-faint)">Emphasis score: ${j.emphasis_score.toFixed(3)}</span>`;
      html += `<div style="display:flex;gap:.8rem;margin-top:.3rem;flex-wrap:wrap">`;
      const comps = [
        ['frequency', j.emphasis_frequency], ['recency', j.emphasis_recency],
        ['marks', j.emphasis_marks], ['syllabus', j.emphasis_syllabus], ['structural', j.emphasis_structural],
      ];
      comps.forEach(([label, val]) => {
        if (val != null) html += `<span class="num" style="font-size:.78rem">${label}: ${val.toFixed(2)}</span>`;
      });
      html += `</div></div>`;
    }
    // Source pages
    if (j.source_pages.length) {
      html += `<div><span style="font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-faint)">Source pages</span><ul style="margin:.3rem 0 0;padding-left:1.2rem">`;
      j.source_pages.forEach(s => { html += `<li><b>${esc(s.document_title)}</b> p.${s.page} — <span style="color:var(--ink-soft)">${esc(s.excerpt.slice(0, 120))}${s.excerpt.length > 120 ? '…' : ''}</span></li>`; });
      html += `</ul></div>`;
    }
    html += `</div></div>`;
    el.innerHTML = html;
  } catch (e) { failed(el, e); }
}

async function planDiff(planId) {
  const rows = await api(`/planning/plans/${planId}/diff`);
  if (!rows.length) return '<div class="empty">No comparable scheduled units.</div>';
  return table(rows, [
    { h: 'Change', f: r => `<span class="chip ${r.change_type === 'unchanged' ? 'ok' : r.change_type === 'removed' ? 'crit' : 'warn'}">${esc(r.change_type)}</span>` },
    { h: 'Lesson', f: r => esc(r.node_label) },
    { h: 'Previous', cls: 'mono', f: r => r.previous_date || '—' },
    { h: 'Now', cls: 'mono', f: r => r.current_date || '—' },
    { h: 'Minutes', right: true, cls: 'num-col', f: r => `${r.previous_minutes ?? '—'} → ${r.current_minutes ?? '—'}` },
  ]);
}

/** This browser's plan, or the newest one already in the database — a
 *  fresh browser has no stored id but the plan still exists. */
async function currentPlan() {
  if (S.plan) return S.plan;
  try {
    const plans = (await api('/planning/plans')).filter(p => p.scheduled_count > 0);
    if (plans.length) { S.plan = plans[0].id; return plans[0].id; }
  } catch {}
  return null;
}

/* ---------- 09 replan ---------- */
$('btn-disrupt').onclick = async () => {
  const el = $('out-disrupt'), cal = $('dis-cal').value, d = $('dis-date').value;
  if (!cal || !d) return said(el, 'Choose a calendar and a date', 'warn');
  working(el, 'Withdrawing that day');
  try {
    const r = await api(`/calendars/${cal}/disrupt`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date: d, reason: 'school closed' }),
    });
    el.innerHTML = `<span class="chip warn">${esc(r.date)} closed</span> <span class="chip">${r.windows_disrupted} window(s) withdrawn</span>`;
  } catch (e) { failed(el, e); }
};

$('btn-replan').onclick = async () => {
  const el = $('out-replan'), cal = $('dis-cal').value;
  if (!cal) return said(el, 'Choose a calendar', 'warn');
  const previous = await currentPlan();
  if (!previous) return said(el, 'Build a plan in stage 08 first', 'warn');
  working(el, 'Replanning, minimising churn against the previous version');
  try {
    const units = await api('/teaching-units');
    const plan = await api('/planning/plans', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        calendar_id: cal, subject: $('plan-subject').value, class_id: $('plan-class').value,
        node_ids: units.map(u => u.node_id), trigger_reason: 'calendar_disruption', parent_version_id: previous,
      }),
    });
    S.plan = plan.plan_version_id;
    el.innerHTML = figures([
      { v: plan.unchanged_count, l: 'lessons unchanged', kind: 'ok' },
      { v: plan.moved_count, l: 'moved', kind: plan.moved_count ? 'warn' : 'ok' },
      { v: plan.unscheduled_unit_ids.length, l: 'dropped', kind: plan.unscheduled_unit_ids.length ? 'crit' : 'ok' },
    ]) + '<p class="aside">The first figure is the one that matters. A replan is judged by how little it disturbs.</p>';
    el.insertAdjacentHTML('beforeend', await planDiff(plan.plan_version_id));
    await schedule(el, plan.plan_version_id, 'out-justification-replan'); ledger();
  } catch (e) { failed(el, e); }
};

/* ---------- 10 generation ---------- */
const VERDICT = { verified: 'ok', partially_supported: 'warn', unsupported: 'crit', not_checked: '' };

function claimList(claims) {
  if (!claims.length) return '<div class="empty">Nothing generated yet.</div>';
  return claims.map(c => `
    <div class="claim">
      <div class="claim-head">
        <span class="chip ${VERDICT[c.verification_status] ?? ''}">${esc(c.verification_status)}</span>
        ${meter(c.confidence)}
      </div>
      <p class="claim-text">${esc(c.text)}</p>
      ${(c.citations || []).map(ci =>
        `<div class="cite"><b>${esc(ci.document_title)}</b> · p.${ci.page} — ${esc(ci.excerpt)}</div>`).join('')}
    </div>`).join('');
}

$('btn-lesson').onclick = async () => {
  const el = $('out-lesson'), id = $('gen-unit').value;
  if (!id) return said(el, 'Build a plan first — lessons are only written for scheduled units', 'warn');
  working(el, 'Retrieving evidence, drafting, then verifying with a second model');
  try {
    el.innerHTML = claimList(await api(`/generation/lessons/${id}`, { method: 'POST' }));
    loadClaims(); ledger();
  } catch (e) { failed(el, e); }
};

$('btn-assess').onclick = async () => {
  const el = $('out-assess'), id = $('gen-node').value;
  if (!id) return said(el, 'Extract a curriculum first', 'warn');
  working(el, 'Drafting practice questions, then verifying each one');
  try {
    el.innerHTML = claimList(await api(`/generation/assessments/${id}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count: +$('gen-count').value }),
    }));
    loadClaims(); ledger();
  } catch (e) { failed(el, e); }
};

async function loadClaims() {
  const el = $('out-claims');
  try {
    const claims = await api('/claims');
    const tally = claims.reduce((a, c) => (a[c.verification_status] = (a[c.verification_status] || 0) + 1, a), {});
    el.innerHTML = (claims.length ? figures([
      { v: tally.verified || 0, l: 'verified', kind: 'ok' },
      { v: tally.partially_supported || 0, l: 'partly supported', kind: 'warn' },
      { v: tally.unsupported || 0, l: 'rejected', kind: 'crit' },
      { v: tally.not_checked || 0, l: 'unchecked' },
    ]) : '') + claimList(claims);
  } catch (e) { failed(el, e); }
}

/* ---------- what each stage loads on entry ---------- */
const ON_ENTER = {
  upload: loadDocuments,
  curriculum: () => { loadDocuments(); loadNodes(); },
  questions: () => { loadDocuments(); loadQuestions(); },
  mapping: async () => { await loadQuestions(); loadNodes(); loadMappings(); },
  corrections: async () => { loadCorrectable(); loadNodes(); loadMastery(); fillSelect($('mast-node'), NODES, n => `${n.syllabus_ref || ''} ${n.label}`.trim()); },
  emphasis: loadNodes,
  calendar: loadCalendars,
  plan: () => { loadCalendars(); loadNodes(); },
  replan: loadCalendars,
  generation: async () => {
    loadNodes(); loadClaims();
    const p = await currentPlan();
    if (p) schedule(null, p);   // fills the lesson picker; no second table wanted here
  },
};

/* ---------- boot ---------- */
(function boot() {
  health();
  ledger();
  show((location.hash || '#upload').slice(1));
})();
