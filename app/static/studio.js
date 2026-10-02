'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = {nodes: [], edges: [], docs: [], claims: [], rows: [], closures: [], source: null,
  plan: localStorage.getItem('studio-plan'), context: JSON.parse(localStorage.getItem('studio-context') || 'null'),
  emphasis: {}, diff: []};
let statusTimer;
function notice(message, error = false, sticky = false) {
  clearTimeout(statusTimer); $('status').textContent = message; $('status').hidden = false;
  $('status').classList.toggle('error', error);
  if (!sticky) statusTimer = setTimeout(() => $('status').hidden = true, error ? 10000 : 4500);
}
async function api(path, body, options = {}) {
  const response = await fetch(path, body === undefined ? options : {...options, method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { const data = await response.json(); message = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail); } catch {}
    throw new Error(message);
  }
  return response.json();
}
async function run(button, label, task) {
  if (button.disabled) return;
  const original = button.innerHTML; button.disabled = true; button.textContent = label; button.setAttribute('aria-busy','true');
  notice(label, false, true);
  try { await task(); $('status').hidden = true; }
  catch (error) { notice(error.message, true); }
  finally { button.disabled = false; button.innerHTML = original; button.removeAttribute('aria-busy'); }
}
function view(name) {
  if (!['overview','sources','plan','evidence'].includes(name)) name='overview';
  document.querySelectorAll('.surface').forEach(el => el.hidden = el.id !== `${name}-view`);
  document.querySelectorAll('button[data-view]').forEach(el => {
    if (el.dataset.view === name) el.setAttribute('aria-current', 'page'); else el.removeAttribute('aria-current');
  });
  if (name === 'evidence') loadClaims().catch(e => notice(e.message, true));
  if (name === 'plan' && state.plan && !state.rows.length) loadPlan().catch(e => notice(e.message, true));
  if(name === 'overview') loadOverview().catch(e=>notice(e.message,true));
  if(location.hash!==`#${name}`) history.pushState(null,'',`#${name}`);
  Atelier.enter(name);
}
document.querySelectorAll('button[data-view]').forEach(el => el.onclick = () => view(el.dataset.view));
window.addEventListener('popstate',()=>view(location.hash.slice(1)));
$('theme').onclick = () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = theme; localStorage.setItem('studio-theme', theme);
};
document.documentElement.dataset.theme = localStorage.getItem('studio-theme') ||
  (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
$('commands').onclick = () => $('palette').showModal();
$('close-palette').onclick = () => $('palette').close();
$('close-inspector').onclick = () => $('inspector').close();
document.querySelectorAll('[data-command]').forEach(el => el.onclick = () => {view(el.dataset.command); $('palette').close();});
document.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {e.preventDefault(); $('palette').showModal();}
});
function saveContext(context) {
  state.context = context; localStorage.setItem('studio-context', JSON.stringify(context));
  $('subject').value = context.subject; $('class-id').value = context.class_id;
  $('calendar').value = context.calendar_id; $('reference-date').value = context.reference_date;
  $('demo-label').textContent = context.synthetic ? 'Biology demo · original synthetic fixtures' : 'Class-level planning by design.';
}
async function refresh() {
  const results = await Promise.allSettled([api('/stats'), api('/documents'), api('/curriculum-nodes'),
    api('/calendars/'), api('/curriculum-edges'), api('/emphasis/')]);
  const failed = results.filter(r => r.status === 'rejected');
  const [stats, docs, nodes, calendars, edges, emphasis] = results.map(r => r.status === 'fulfilled' ? r.value : null);
  if (stats) {
    $('connection').textContent = '● Connected';
    $('pipeline-counts').innerHTML = [['documents','sources'],['objectives','objectives'],['questions','questions'],['scheduled','sessions']]
      .map(([key,label]) => `<span><b>${stats[key]}</b> ${label}</span>`).join('');
  }
  if (docs) {state.docs = docs; renderDocuments();}
  if (nodes) state.nodes = nodes;
  if (edges) state.edges = edges;
  if (emphasis) state.emphasis = Object.fromEntries(emphasis.map(r => [r.node_id, r.score]));
  renderGraph();
  if (calendars) {
    const selected = $('calendar').value || state.context?.calendar_id;
    $('calendar').innerHTML = calendars.map(c => `<option value="${esc(c.id)}">${esc(c.school_id)} · ${c.term_start}</option>`).join('');
    if (selected && calendars.some(c => c.id === selected)) $('calendar').value = selected;
    if (!$('reference-date').value && calendars.length) $('reference-date').value = calendars.find(c => c.id === $('calendar').value)?.term_start;
  }
  if (state.context) saveContext(state.context);
  if (failed.length) {
    if (!stats) $('connection').textContent = '○ Database unavailable';
    notice(failed[0].reason.message, true);
  }
}
function renderDocuments() {
  $('doc-count').textContent = state.docs.length;
  $('documents').classList.remove('skeleton');
  const query=$('source-search').value.trim().toLowerCase();
  const matching=state.docs.filter(d=>(d.title+' '+d.doc_type).toLowerCase().includes(query));
  $('documents').innerHTML = matching.length ? matching.map(d => `<button class="document ${state.source === d.id ? 'selected' : ''}" data-document="${d.id}"><strong>${esc(d.title)}</strong><small>${esc(d.doc_type.replaceAll('_',' '))} · ${d.span_count} passages</small></button>`).join('') : '<div class="empty"><p>No sources to show. Add a document, try the demo, or clear your search.</p></div>';
  document.querySelectorAll('[data-document]').forEach(el => el.onclick = () => selectDocument(el.dataset.document).catch(e => notice(e.message,true)));
}
async function selectDocument(id) {
  state.source = id; renderDocuments(); $('reader').innerHTML = '<div class="skeleton">Resolving source passages…</div>';
  const [spans, curriculum] = await Promise.all([api(`/documents/${id}/spans`), api(`/studio/documents/${id}/curriculum`)]);
  if(state.source !== id) return;
  state.sourceNodes = curriculum.nodes; renderGraph();
  $('setup-plan').disabled = curriculum.stale || !curriculum.nodes.some(n=>n.node_type==='objective');
  $('source-scope').textContent = curriculum.stale ? 'Source changed. Extract objectives again.' : curriculum.extraction.partial ? 'Partial extraction: review the inspected objectives before planning.' : 'Objectives attributed to this document. Review before planning.';
  $('reader-title').textContent = state.docs.find(d => d.id === id)?.title || 'Source passages';
  $('extract').disabled = false;
  $('reader').innerHTML = spans.length ? spans.map(s => `<div class="source-span"><small>PAGE ${s.page > 0 ? s.page : '?'} · ${esc(s.precision)} attribution</small><p>${esc(s.text)}</p><button class="quiet" data-span="${s.id}">Inspect evidence ↗</button></div>`).join('') : '<div class="empty">No extracted passages.</div>';
  $('reader').querySelectorAll('[data-span]').forEach(el => el.onclick = () => openEvidence([spans.find(s => s.id === el.dataset.span)]));
}
function renderGraph() {
  const nodes = (state.sourceNodes || []).filter(n => n.node_type === 'objective');
  $('objective-count').textContent = `${nodes.length} objectives`;
  $('objectives').innerHTML = nodes.slice(0,20).map(n => `<div class="objective"><div class="confidence" title="Confidence ${Math.round(n.confidence*100)}%"><i style="width:${Math.round(n.confidence*100)}%"></i></div><div>${esc(n.label)}<small>${esc(n.syllabus_ref || 'No curriculum code')} · ${esc(n.origin.replaceAll('_',' '))}</small></div></div>`).join('') || '<div class="empty"><p>Your curriculum map will appear here.</p></div>';
  const display = nodes.slice(0,16), positions = {};
  display.forEach((n,i) => {const angle = 2*Math.PI*i/display.length - Math.PI/2; positions[n.id] = [170+Math.cos(angle)*115, 95+Math.sin(angle)*67];});
  const lines = state.edges.filter(e => e.edge_type === 'prerequisite' && positions[e.source_node_id] && positions[e.target_node_id]).map(e => {
    const [x1,y1] = positions[e.source_node_id], [x2,y2] = positions[e.target_node_id];
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" marker-end="url(#arrow)"/>`;
  }).join('');
  $('graph').innerHTML = display.length ? `<svg viewBox="0 0 340 190" role="img" aria-label="Objective prerequisite graph"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="11" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="currentColor"/></marker></defs>${lines}${display.map(n=>{const [x,y]=positions[n.id];return `<g><title>${esc(n.label)} · ${Math.round(n.confidence*100)}% confidence</title><circle cx="${x}" cy="${y}" r="8" opacity="${Math.max(.35,n.confidence)}" ${n.confidence<.7?'stroke-dasharray="2 2"':''}/><text x="${x}" y="${y+20}" text-anchor="middle">${esc(n.label.length>19?n.label.slice(0,17)+'…':n.label)}</text></g>`;}).join('')}</svg>` : '';
}
$('source-search').oninput = renderDocuments;
$('refresh').onclick = () => run($('refresh'), 'Refreshing…', refresh);
$('upload-form').onsubmit = e => {
  e.preventDefault(); const button = e.target.querySelector('button');
  run(button, 'Parsing document…', async () => {
    const form = new FormData(e.target);
    const job = await api('/ingestion/jobs', undefined, {method:'POST', body:form});
    const data = await new Promise((resolve,reject)=>{
      const stream=new EventSource(job.events_url);
      stream.onmessage=event=>{const progress=JSON.parse(event.data);notice(progress.message,false,true);
        if(progress.status==='completed'){stream.close();resolve(progress.result);}
        if(progress.status==='failed'){stream.close();reject(new Error(progress.message));}
      };
      stream.onerror=()=>{stream.close();reject(new Error('Progress stream disconnected. Refresh the library to check whether parsing completed.'));};
    });
    await refresh(); await selectDocument(data.id); e.target.reset();
  });
};
$('extract').onclick = () => run($('extract'), 'Extracting objectives…', async () => {
  await api(`/ingestion/documents/${state.source}/curriculum`, {}); await refresh(); await selectDocument(state.source);
});
$('public-syllabus').onclick=()=>run($('public-syllabus'),'Loading public syllabus…',async()=>{
  const result=await api('/demo/public-syllabus',{});await refresh();await selectDocument(result.document_id);
});
async function requestBody(parent = null) {
  const units = await api('/teaching-units');
  state.units=units;
  let nodeIds = [];
  if (state.context?.calendar_id === $('calendar').value) nodeIds = state.context.node_ids;
  if (!nodeIds.length) throw new Error('Select a saved plan in Overview, or create a plan from your source.');
  if (!$('calendar').value) throw new Error('Choose a calendar first.');
  return {calendar_id:$('calendar').value, subject:$('subject').value, class_id:$('class-id').value,
    node_ids:nodeIds, parent_version_id:parent, trigger_reason:parent?'calendar_disruption':'initial_plan',
    coverage_preference:Number($('coverage').value), minimum_duration_ratio:Number($('duration-ratio').value)};
}
function metrics(result, preview = false) {
  $('plan-metrics').innerHTML = [[`${Math.round(result.weighted_coverage*100)}%`,'Weighted coverage'],
    [result.unchanged_count,'Unchanged units'], [result.shortened_count,'Shortened units'],
    [`${Math.round(result.solve_time_ms)} ms`,preview?'Preview solve time':'Solver time']]
    .map(([number,label])=>`<div><strong>${esc(number)}</strong><span>${label}</span></div>`).join('');
  const names = Object.fromEntries((state.units || []).map(r => [r.id,r.node_label]));
  $('plan-explanations').innerHTML = Object.entries(result.explanations || {}).map(([id,reason]) => `<p><b>${esc(names[id] || 'Unscheduled objective')}:</b> ${esc(reason)}</p>`).join('');
  if(result.conflict_unit_ids?.length)$('plan-explanations').insertAdjacentHTML('beforeend',`<details><summary>Solver conflict set (${result.conflict_unit_ids.length} objectives)</summary><p>${result.conflict_unit_ids.map(id=>esc(names[id] || id)).join(' · ')}</p><p class="muted">CP-SAT found these coverage requirements cannot jointly fit. This is a sufficient conflict set, not necessarily the smallest one.</p></details>`);
}
async function buildPlan(parent = null) {
  const result = await api('/planning/plans', await requestBody(parent));
  state.plan = result.plan_version_id; localStorage.setItem('studio-plan', state.plan);
  state.diff = parent ? await api(`/planning/plans/${state.plan}/diff`) : [];
  await loadPlan(); metrics(result); renderDiff(); await refresh(); view('plan');
}
$('build').onclick = () => run($('build'), 'Finding the best fit…', () => buildPlan());
$('demo').onclick = () => run($('demo'), 'Preparing Biology demo…', async () => {
  const context = await api('/demo/studio', {}); await refresh(); saveContext(context);
  await selectDocument(context.document_id); $('disruption').value = 'Snow day Thursday + sports day next Tuesday';
  $('duration-ratio').value = '0.66'; await buildPlan();
});
async function loadPlan() {
  if (!state.plan) return;
  const report = await api(`/studio/plans/${state.plan}/coverage`);
  saveContext({...state.context,...report.context,reference_date:state.context?.reference_date || new Date().toISOString().slice(0,10)});
  const rows = await api(`/planning/plans/${state.plan}`);
  state.rows = rows;
  $('plan-title').textContent = `${$('subject').value} · ${$('class-id').value}`;
  renderTimeline();
  $('lesson-picker').innerHTML = rows.map(r=>`<option value="${r.id}">${r.date} · ${esc(r.node_label)}</option>`).join('');
  const summary=await api(`/planning/plans/${state.plan}/summary`);
  if(summary.metrics)metrics(summary.metrics);
  await loadOverview(); await loadPlanChoices();
}
function renderTimeline() {
  const oldPositions = new Map([...$('timeline').querySelectorAll('[data-lesson]')].map(el=>[el.dataset.lesson,el.getBoundingClientRect()]));
  if (!state.rows.length) { $('timeline').innerHTML = '<div class="empty">No lessons fit this calendar. Review the solver explanations and teaching durations.</div>'; return; }
  const changes = Object.fromEntries(state.diff.map(r=>[r.unit_id,r.change_type]));
  const sessionKeys = new Map(); const counts = {};
  state.rows.forEach(row => {const uid=row.teaching_unit_id;const index=counts[uid] || 0;counts[uid]=index+1;sessionKeys.set(row.id,`${uid}-${index}`);});
  const start = new Date(state.rows[0].date+'T12:00:00');
  start.setDate(start.getDate() - (start.getDay()+6)%7);
  const last = new Date(state.rows[state.rows.length-1].date+'T12:00:00');
  const weeks = [];
  for (let monday=new Date(start); monday<=last; monday.setDate(monday.getDate()+7)) {
    const days = [];
    const weekend = state.rows.some(r=>{const d=new Date(r.date+'T12:00:00');return d.getDay()===0 || d.getDay()===6;});
    for (let i=0;i<(weekend?7:5);i++) {
      const day=new Date(monday); day.setDate(day.getDate()+i);
      const key = `${day.getFullYear()}-${String(day.getMonth()+1).padStart(2,'0')}-${String(day.getDate()).padStart(2,'0')}`;
      const lessons = state.rows.filter(r=>r.date===key);
      days.push(`<div class="day"><div class="day-label"><span>${day.toLocaleDateString('en',{weekday:'short'})}</span><span>${day.toLocaleDateString('en',{day:'numeric',month:'short'})}</span></div>${lessons.map(r=>{
        const change=changes[r.teaching_unit_id] || r.status, emphasis=state.emphasis[r.node_id] ?? r.priority;
        return `<button class="lesson" data-lesson="${sessionKeys.get(r.id)}" data-scheduled="${r.id}" data-unit="${r.teaching_unit_id}" data-change="${esc(change)}" style="min-height:${Math.max(60,r.scheduled_minutes*1.15)}px;background-color:color-mix(in srgb,var(--accent) ${Math.round(5+emphasis*13)}%,var(--surface))"><strong>${change==='moved'?'↗ ':change==='compressed'?'↘ ':change==='unchanged'?'○ ':''}${esc(r.node_label)}</strong><small>${r.start_time?.slice(0,5) || ''} · ${r.scheduled_minutes} min</small><small>${Math.round(emphasis*100)}% emphasis · why? ↗</small></button>`;
      }).join('')}</div>`);
    }
    weeks.push(`<div class="week ${weekend?'seven-days':''}">${days.join('')}</div>`);
  }
  $('timeline').innerHTML = weeks.join('');
  $('timeline').querySelectorAll('[data-unit]').forEach(el=>el.onclick=()=>inspectLesson(el.dataset.unit,el.dataset.scheduled).catch(e=>notice(e.message,true)));
  if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
    $('timeline').querySelectorAll('[data-lesson]').forEach(el=>{
      const old=oldPositions.get(el.dataset.lesson); if (!old) return;
      const now=el.getBoundingClientRect();
      el.animate([{transform:`translate(${old.x-now.x}px,${old.y-now.y}px)`},{transform:'translate(0,0)'}],{duration:650,easing:'cubic-bezier(.2,.7,.2,1)'});
    });
  }
}
function renderDiff() {
  $('diff').innerHTML = state.diff.length ? `<article class="card"><h3>A smaller change. A steadier term.</h3>${state.diff.map(r=>`<div class="diff-item"><span class="status-tag">${esc(r.change_type)}</span><b>${esc(r.node_label)}</b><span>${r.previous_date || '—'} → ${r.current_date || '—'} · ${r.previous_minutes ?? '—'} → ${r.current_minutes ?? '—'} min</span></div>`).join('')}</article>` : '';
}
async function inspectLesson(unitId,sessionId) {
  const result=await api(`/planning/plans/${state.plan}/units/${unitId}/justification${sessionId?'?scheduled_session_id='+sessionId:''}`);
  $('inspector-title').textContent=result.node_label;
  $('inspector-content').innerHTML=`<p class="eyebrow">WHY THIS LESSON?</p><p>${esc(result.node_description || 'No objective description recorded.')}</p><div class="metrics"><div><strong>${result.scheduled_minutes}</strong><span>Minutes in this session</span></div><div><strong>${result.emphasis_score==null?'—':Math.round(result.emphasis_score*100)+'%'}</strong><span>Assessment emphasis</span></div><div><strong>${result.days_to_term_end??'—'}</strong><span>Days to term end</span></div><div><strong>${result.was_moved?'Moved':'Steady'}</strong><span>Plan context</span></div></div><h3>Prerequisites</h3><p>${result.prerequisites.map(p=>esc(p.node_label)).join(' · ') || 'No prerequisites recorded.'}</p><h3>Source pages</h3>${result.source_pages.map(s=>`<div class="source-span"><small>${esc(s.document_title)} · page ${s.page}</small><p>${esc(s.excerpt)}</p></div>`).join('') || '<p class="muted">No exam-question source page is linked to this objective yet. Inspect the source library for teaching evidence.</p>'}`;
  if(sessionId){
    const taught=state.rows.find(r=>r.id===sessionId)?.status==='taught';
    $('inspector-content').insertAdjacentHTML('beforeend',`<button id="mark-taught" class="primary" ${taught?'disabled':''}>${taught?'Session already taught':'Mark this session taught'}</button><p class="muted">Taught sessions retain their original window and duration in future replans.</p>`);
    $('mark-taught').onclick=()=>run($('mark-taught'),'Saving taught session…',async()=>{await api(`/planning/plans/${state.plan}/sessions/${sessionId}/taught`,{});$('inspector').close();await loadPlan();});
  }
  $('inspector').showModal();
}
$('preview-disruption').onclick=()=>run($('preview-disruption'),'Interpreting dates…',async()=>{
  if (!$('calendar').value || !$('reference-date').value) throw new Error('Choose a calendar and reference date.');
  const result=await api(`/calendars/${$('calendar').value}/disruptions/preview`,{text:$('disruption').value,reference_date:$('reference-date').value,allow_ai:$('allow-ai').checked});
  state.closures=result.dates;
  $('closure-preview').innerHTML=`<p class="muted"><b>Closure preview</b><br>${result.dates.map(d=>esc(d)).join('<br>')}<br>${esc(result.interpretation)}<br>Parser: ${esc(result.parser)}</p>`;
});
$('disruption').oninput=()=>{state.closures=[];$('closure-preview').innerHTML='';};
$('reference-date').onchange=$('disruption').oninput;
$('calendar').onchange=()=>{state.closures=[];$('closure-preview').innerHTML='';};
$('preview-plan').onclick=()=>run($('preview-plan'),'Previewing tradeoff…',async()=>{
  const result=await api('/planning/preview',await requestBody(state.plan)); metrics(result,true);
  notice('Preview only: the saved plan is unchanged.');
});
$('replan').onclick=()=>run($('replan'),'Applying closures and replanning…',async()=>{
  if (!state.plan) throw new Error('Build a plan first.');
  if (!state.closures.length) throw new Error('Preview the closure dates first.');
  await api(`/calendars/${$('calendar').value}/disruptions`,{dates:state.closures});
  const previous=state.plan; await buildPlan(previous); state.closures=[];$('closure-preview').innerHTML='';
});
$('coverage').oninput=()=>{$('preview-plan').textContent=`Preview tradeoff · ${Math.round(Number($('coverage').value)*100)}% coverage preference`;};
$('forecast').onclick=()=>run($('forecast'),'Testing disruption scenarios…',async()=>{
  const body=await requestBody(state.plan);body.samples=100;body.disruption_rate=Number($('closure-rate').value);body.seed=42;
  const report=await api('/planning/resilience',body), percent=Math.round(report.high_emphasis_coverage_probability*100);
  $('forecast-result').innerHTML=`<div class="forecast-number">${percent}%</div><p class="muted">Chance all high-emphasis objectives fit.<br>95% sampling interval: ${report.confidence_interval.map(v=>Math.round(v*100)+'%').join(' – ')} · ${report.samples} scenarios</p><div class="forecast-track"><i style="width:${percent}%"></i></div>${report.at_risk_units.slice(0,4).map(r=>`<p class="muted">${esc(r.label)} <b>${Math.round(r.miss_probability*100)}% at risk</b></p>`).join('')}<p class="muted">Add calendar capacity around the at-risk objectives, then compare forecasts. Seed: ${report.seed}.</p><p class="muted">${esc(report.assumption)} ${report.incomplete_solves?`${report.incomplete_solves} scenarios used feasible or fallback results; solver uncertainty is additional to the sampling interval.`:''}</p>`;
});
$('ics').onclick=()=>{if (!state.plan) return notice('Build a plan first.',true);window.location.href=`/planning/plans/${state.plan}/export.ics`;};
$('print').onclick=()=>{if (!state.plan) return notice('Load a plan first.',true);window.location.href=`/planning/plans/${state.plan}/export.pdf`;};
async function loadClaims() {
  state.claims=await api('/claims');
  $('claims').innerHTML=state.claims.length?state.claims.map(c=>`<button class="claim" data-claim="${c.id}"><span class="status-tag ${esc(c.verification_status)}">${esc(c.verification_status.replaceAll('_',' '))}</span><p>${esc(c.text)}</p><small>${c.citations.length} source passages · ${Math.round(c.confidence*100)}% verifier confidence · inspect ↗</small></button>`).join(''):'<div class="empty"><h3>Evidence comes first.</h3><p>Generated claims will appear here with their verification status. Try the demo for inspectable source fixtures.</p></div>';
  $('claims').querySelectorAll('[data-claim]').forEach(el=>el.onclick=async()=>{
    try {const spans=await api(`/evidence/claims/${el.dataset.claim}`);await openEvidence(spans,state.claims.find(c=>c.id===el.dataset.claim));}catch(e){notice(e.message,true);}
  });
  const health=await api('/health/providers');
  $('provider-health').innerHTML=health.events.length?health.events.slice(-5).reverse().map(e=>`<p>${esc(e.provider)} · ${esc(e.status)} · ${e.elapsed_ms} ms${e.circuit_open?' · circuit open':''}</p>`).join(''):'No provider calls yet. The sample demo works without external AI.';
}
$('reload-claims').onclick=()=>run($('reload-claims'),'Loading claims…',loadClaims);
$('generate').onclick=()=>run($('generate'),'Retrieving, drafting, and verifying…',async()=>{
  if (!$('lesson-picker').value) throw new Error('Build a plan first.');
  await api(`/generation/lessons/${$('lesson-picker').value}`,{});await loadClaims();
});
async function openEvidence(spans, claim = null) {
  $('inspector-title').textContent=claim?'Claim → source':'Source passage';
  if (!spans.length) {$('inspector-content').innerHTML='<p>No resolvable evidence was cited. This claim cannot be presented as supported.</p>';$('inspector').showModal();return;}
  const s=spans[0];
  $('inspector-content').innerHTML=`${claim?`<p>${esc(claim.text)}</p><span class="status-tag ${esc(claim.verification_status)}">${esc(claim.verification_status)}</span>`:''}<div class="inspection"><div><p class="eyebrow">${esc(s.document_title)} · PAGE ${s.page>0?s.page:'UNKNOWN'}</p><blockquote>${esc(s.text)}</blockquote><p class="muted">Attribution precision: <b>${esc(s.precision)}</b>. Page-level parsers do not establish an exact sentence bounding box.</p><code>${esc(s.content_hash)}</code>${spans.slice(1).map(other=>`<blockquote>${esc(other.text)}</blockquote>`).join('')}</div><div id="pdf-preview" class="pdf-frame"><div class="muted">Opening original PDF if available…</div></div></div>`;
  if (!$('inspector').open) $('inspector').showModal();
  try {
    const response=await fetch(s.file_url);if(!response.ok) throw new Error('Original PDF unavailable. The extracted source passage is shown beside this panel.');
    const bytes=await response.arrayBuffer();
    // PDF.js is bundled locally. A native PDF preview is the fallback.
    try {
      const pdfjs=await import('/vendor/pdfjs/pdf.mjs');
      pdfjs.GlobalWorkerOptions.workerSrc='/vendor/pdfjs/pdf.worker.mjs';
      const pdf=await pdfjs.getDocument({data:bytes}).promise;const page=await pdf.getPage(Math.max(1,s.page));
      const viewport=page.getViewport({scale:1});
      const canvas=document.createElement('canvas');canvas.width=viewport.width;canvas.height=viewport.height;
      $('pdf-preview').replaceChildren(canvas);await page.render({canvasContext:canvas.getContext('2d'),viewport}).promise;
      const content=await page.getTextContent();const normalize=t=>t.toLowerCase().replace(/\s+/g,' ').trim();
      let text='',runs=[];
      for(const item of content.items){if(!item.str?.trim())continue;const value=normalize(item.str);const start=text.length;text+=value+' ';runs.push({item,start,end:start+value.length});}
      const needle=normalize(s.text),match=text.indexOf(needle);
      if(match>=0){
        for(const run of runs.filter(r=>r.end>match&&r.start<match+needle.length)){
          const transform=pdfjs.Util.transform(viewport.transform,run.item.transform);
          const height=Math.hypot(transform[2],transform[3]);const overlay=document.createElement('div');overlay.className='bbox-overlay';
          overlay.style.cssText=`left:${transform[4]/viewport.width*100}%;top:${(transform[5]-height)/viewport.height*100}%;width:${run.item.width/viewport.width*100}%;height:${height/viewport.height*100}%`;
          overlay.title='Matching extracted text run';$('pdf-preview').append(overlay);
        }
      }
    } catch {
      $('pdf-preview').innerHTML=`<iframe title="Original source PDF" src="${esc(s.file_url)}#page=${Math.max(1,s.page)}"></iframe><p class="muted">Native PDF preview · page-level navigation.</p>`;
    }
  } catch(e){$('pdf-preview').innerHTML=`<div class="empty"><span class="empty-icon">⌑</span><p>${esc(e.message)}</p></div>`;}
}
$('audit').onclick=()=>run($('audit'),'Checking source matches…',async()=>{
  const text=$('audit-text').value;if(!text.trim())throw new Error('Paste some lesson content to audit.');
  const result=await api('/evidence/audit',{text});
  $('audit-results').innerHTML=`<p class="muted"><b>${result.exact_matches}/${result.total} exact matches</b> · ${result.review_required} need review<br>${esc(result.method)}</p>${result.claims.map(c=>`<div class="audit-row"><span class="status-tag ${esc(c.status)}">${esc(c.status.replaceAll('_',' '))}</span><p>${esc(c.text)}</p><p class="muted">${esc(c.reason)}</p>${c.excerpts.length?`<details><summary>Related source passages</summary>${c.excerpts.map(t=>`<p>${esc(t)}</p>`).join('')}</details>`:''}</div>`).join('')}`;
});
$('calibrate').onclick=()=>run($('calibrate'),'Validating corrected mappings…',async()=>{
  const report=await api('/corrections/calibrate',{});
  $('calibration-result').innerHTML=`<p class="muted">${report.accepted?'Weights adopted':'Existing weights retained'} · ${report.train_samples} training mappings / ${report.validation_samples} held out<br>Validation mean squared error: ${report.baseline_validation_mse.toFixed(4)} → ${report.calibrated_validation_mse.toFixed(4)}<br>${esc(report.note)}</p>`;
});
async function boot() {
  await refresh();
  if (state.source) await selectDocument(state.source);
  if (state.plan) {
    try {await loadPlan();}catch{state.plan=null;localStorage.removeItem('studio-plan');}
  } else {
    const plans=await api('/planning/plans');if(plans.length){state.plan=plans[0].id;await loadPlan();}
  }
  const requested=location.hash.slice(1);view(['overview','sources','plan','evidence'].includes(requested)?requested:'overview');
}
// The control-room extension starts boot after wiring the complete workflow.
