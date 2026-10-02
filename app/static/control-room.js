'use strict';

async function loadPlanChoices() {
  const plans=await api('/planning/plans');
  $('plan-switcher').innerHTML=plans.length?plans.map((p,i)=>`<option value="${p.id}">${esc(p.trigger_reason || 'Term plan')} · ${new Date(p.created_at).toLocaleString()}${i===0?' · latest':''}</option>`).join(''):'<option>No saved plans</option>';
  if(state.plan)$('plan-switcher').value=state.plan;
}
$('plan-switcher').onchange=async()=>{try{
  state.plan=$('plan-switcher').value; localStorage.setItem('studio-plan',state.plan);state.diff=[];state.closures=[];
  await loadPlan();renderDiff();
}catch(e){notice(e.message,true);}};
async function loadOverview(){
  if(!state.plan){await loadPlanChoices();return;}
  const report=await api(`/studio/plans/${state.plan}/coverage`), t=report.totals;
  const percent=t.objectives?Math.round(t.scheduled/t.objectives*100):0;
  $('overview-content').innerHTML=`<div class="overview-grid"><article class="coverage-hero"><div><p class="eyebrow">${esc(report.context.subject)} / ${esc(report.context.class_id)}</p><h2>Every objective.<br>A place to grow.</h2><p>${t.scheduled} of ${t.objectives} objectives have teaching time.<br>${t.taught} fully taught. Your next lesson is waiting.</p><button id="open-planner" class="primary">Open your planner ↗</button></div><div class="coverage-ring" style="--coverage:${percent}%"><div><strong>${percent}%</strong><span>scheduled</span></div></div></article><article class="card readiness"><p class="eyebrow">TRUST, MADE VISIBLE</p><h3>A clearer picture.</h3><div><strong>${t.objectives-t.scheduled}</strong><span>objectives without teaching time</span></div><div><strong>${t.without_sources}</strong><span>objectives without source attribution</span></div><div><strong>${t.without_verified_claims}</strong><span>objectives without verified lesson claims</span></div><p class="muted">A scheduled objective is not proof of learning. Source attribution is not claim verification.</p></article></div><article class="card ledger-card"><div class="card-title"><div><p class="eyebrow">COVERAGE LEDGER</p><h3>The details that make a difference.</h3></div><input id="ledger-search" placeholder="Find an objective…" aria-label="Find an objective"></div><div class="table-scroll"><table class="ledger"><thead><tr><th>Learning objective</th><th>Teaching status</th><th>Time / preferred</th><th>Evidence</th><th></th></tr></thead><tbody id="ledger-rows"></tbody></table></div><p class="muted">${esc(report.note)}${report.context.legacy_scope?' This older plan includes only recoverable scheduled objectives.':''}</p></article>`;
  $('open-planner').onclick=()=>view('plan');
  const render=()=>{
    const query=$('ledger-search').value.toLowerCase();
    $('ledger-rows').innerHTML=report.objectives.filter(r=>(r.label+' '+r.reference).toLowerCase().includes(query)).map(r=>`<tr><td><strong>${esc(r.label)}</strong><small>${esc(r.reference || 'No curriculum code')}</small></td><td><span class="status-tag ${r.status}">${esc(r.status.replaceAll('_',' '))}</span></td><td>${r.scheduled_minutes} / ${r.preferred_minutes} min<small>${r.taught_minutes} min taught</small></td><td>${r.source_ids.length?'● Source attributed':'○ Source needed'}<small>${r.verified_claims} verified claims</small></td><td>${r.session_id?`<button class="quiet" data-ledger-unit="${r.unit_id}" data-session="${r.session_id}" aria-label="Inspect ${esc(r.label)}">Inspect ↗</button>`:'—'}</td></tr>`).join('') || '<tr><td colspan="5">No matching objectives.</td></tr>';
    document.querySelectorAll('[data-ledger-unit]').forEach(b=>b.onclick=()=>inspectLesson(b.dataset.ledgerUnit,b.dataset.session).catch(e=>notice(e.message,true)));
  };$('ledger-search').oninput=render;render();
}

document.body.insertAdjacentHTML('beforeend',`<dialog id="setup-dialog"><div class="dialog-head"><div><p class="eyebrow">SOURCE → TEACHING TIME</p><h2>Build your first term.</h2></div><button id="close-setup" class="quiet">Close ×</button></div><form id="setup-form"><div class="setup-grid"><div><label>Subject<input name="subject" required maxlength="120" placeholder="Biology"></label><label>Class<input name="class_id" required maxlength="120" placeholder="Year 10"></label><div class="form-pair"><label>Term starts<input name="term_start" type="date" required></label><label>Term ends<input name="term_end" type="date" required></label></div><fieldset><legend>Teaching days</legend><div class="weekday-picker">${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map((d,i)=>`<label><input name="weekdays" type="checkbox" value="${i}" ${i<5?'checked':''}>${d}</label>`).join('')}</div></fieldset><div class="form-pair"><label>Start time<input name="start_time" type="time" value="09:00" required></label><label>Minutes per session<input name="session_minutes" type="number" min="20" max="180" value="60" required></label></div><label>Preferred minutes per new objective<input name="objective_minutes" type="number" min="20" max="360" value="60" required></label><p class="muted">One session per selected day. Existing teaching-unit durations are retained. You can refine the timetable in Advanced workflow.</p></div><div><h3>Review the learning objectives</h3><p class="muted">Choose what belongs in this term. Include prerequisite objectives needed by later lessons.</p><div id="setup-objectives"></div></div></div><div class="dialog-footer"><span class="muted">Solver-backed scheduling · no student data</span><button class="primary" type="submit">Create calendar & plan →</button></div></form></dialog><dialog id="recovery-dialog"><div class="dialog-head"><div><p class="eyebrow">RECOVERY LAB / COMPARE BEFORE YOU COMMIT</p><h2>One disruption. Three ways forward.</h2></div><button id="close-recovery" class="quiet">Close ×</button></div><p id="recovery-context" class="muted"></p><div id="recovery-options" class="recovery-options"></div><p class="muted">These are actual solver results, not AI suggestions. Applying saves the exact reviewed assignments and closes only this class’s affected windows. Taught sessions stay fixed. Comparisons expire after one hour or when inputs change.</p></dialog>`);
$('close-setup').onclick=()=>$('setup-dialog').close();
$('close-recovery').onclick=()=>$('recovery-dialog').close();
$('setup-plan').onclick=()=>{
  const form=$('setup-form');form.elements.subject.value=state.docs.find(d=>d.id===state.source)?.title.slice(0,120) || '';
  const start=new Date();const end=new Date();end.setDate(end.getDate()+27);
  form.elements.term_start.value=start.toISOString().slice(0,10);form.elements.term_end.value=end.toISOString().slice(0,10);
  $('setup-objectives').innerHTML=(state.sourceNodes || []).filter(n=>n.node_type==='objective').map(n=>`<label class="objective-choice"><input type="checkbox" name="node_ids" value="${n.id}" checked><span>${esc(n.label)}<small>${esc(n.syllabus_ref || 'Review extracted objective')}</small></span></label>`).join('');
  $('setup-dialog').showModal();
};
$('setup-form').onsubmit=e=>{
  e.preventDefault();const form=e.target,button=form.querySelector('[type=submit]');
  run(button,'Building your term…',async()=>{
    const data=new FormData(form),body=Object.fromEntries(data);
    body.document_id=state.source;body.node_ids=data.getAll('node_ids');body.weekdays=data.getAll('weekdays').map(Number);
    for(const key of ['session_minutes','objective_minutes'])body[key]=Number(body[key]);
    if(!body.node_ids.length || !body.weekdays.length)throw new Error('Choose at least one objective and teaching day.');
    const result=await api('/studio/setup',body);await refresh();saveContext(result);
    state.plan=result.plan_id;localStorage.setItem('studio-plan',state.plan);state.diff=[];
    await loadPlan();renderDiff();$('setup-dialog').close();view('overview');
  });
};
$('replan').textContent='Compare recovery strategies →';
$('replan').onclick=()=>run($('replan'),'Solving three recovery strategies…',async()=>{
  if(!state.plan)throw new Error('Build a plan first.');
  if(!state.closures.length)throw new Error('Preview closure dates first.');
  const comparison=await api(`/studio/plans/${state.plan}/recovery`,{dates:state.closures,minimum_duration_ratio:Number($('duration-ratio').value)});
  $('recovery-context').textContent=`Closures: ${comparison.dates.join(' · ')}. Your saved timetable is unchanged until you apply a strategy.`;
  $('recovery-options').innerHTML=comparison.options.map(o=>`<article class="strategy ${o.key==='coverage'?'highlight':''}"><p class="eyebrow">${o.key==='depth'?'01 / DEPTH':o.key==='balanced'?'02 / BALANCE':'03 / COVERAGE'}</p><h3>${esc(o.label)}</h3><div class="strategy-score">${Math.round(o.result.weighted_coverage*100)}<span>%</span></div><p class="muted">weighted curriculum coverage</p><dl><div><dt>Minimum teaching time</dt><dd>${Math.round(o.ratio*100)}%</dd></div><div><dt>New or moved sessions</dt><dd>${o.moved_sessions}</dd></div><div><dt>Shortened objectives</dt><dd>${o.result.shortened_count}</dd></div><div><dt>Teaching minutes lost</dt><dd>${o.minutes_lost}</dd></div></dl><p class="strategy-note">${o.omitted.length?`${o.omitted.length} objectives omitted: ${o.omitted.map(esc).join(', ')}`:'All objectives have teaching time.'}</p><small>${Math.round(o.result.solve_time_ms)} ms · ${esc(o.result.status || 'solver result')}</small><button class="${o.key==='coverage'?'primary':'quiet'} full" data-strategy="${o.key}">Apply this strategy →</button></article>`).join('');
  document.querySelectorAll('[data-strategy]').forEach(button=>button.onclick=()=>run(button,'Applying reviewed plan…',async()=>{
    const result=await api(`/studio/recovery/${comparison.scenario_id}/apply`,{option:button.dataset.strategy});
    state.plan=result.plan_id;localStorage.setItem('studio-plan',state.plan);
    state.diff=await api(`/planning/plans/${state.plan}/diff`);state.closures=[];$('closure-preview').innerHTML='';
    await loadPlan();renderDiff();$('recovery-dialog').close();view('plan');
  }));$('recovery-dialog').showModal();
});
boot().then(loadPlanChoices).catch(e=>notice(e.message,true));
