(() => {
  const role = document.body.dataset.role;
  const $ = id => document.getElementById(id);
  const savedTheme = localStorage.getItem('studio-theme');
  document.documentElement.dataset.theme = savedTheme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  function updateThemeLabel() {
    const dark = document.documentElement.dataset.theme === 'dark';
    $('theme-toggle').setAttribute('aria-label', `Switch to ${dark ? 'light' : 'dark'} mode`);
    $('theme-toggle').title = `Switch to ${dark ? 'light' : 'dark'} mode`;
  }
  $('theme-toggle').onclick = () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    localStorage.setItem('studio-theme', next);
    updateThemeLabel();
  };
  updateThemeLabel();
  const state = {user: null, mode: 'register', editing: null};
  let messageTimer;
  const text = (tag, value, className) => {
    const node = document.createElement(tag);
    node.textContent = value;
    if (className) node.className = className;
    return node;
  };
  const show = (message, error = false) => {
    const box = $('message');
    box.textContent = message;
    box.hidden = false;
    box.classList.toggle('error', error);
    box.classList.toggle('success', !error);
    clearTimeout(messageTimer);
    messageTimer = setTimeout(() => { box.hidden = true; }, error ? 9000 : 6000);
  };
  async function api(path, options = {}) {
    const response = await fetch(`/classroom${path}`, {
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      ...options
    });
    let data;
    try { data = await response.json(); } catch { data = {}; }
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status})`);
    return data;
  }
  async function busy(button, action) {
    button.disabled = true;
    try { await action(); } catch (error) { show(error.message, true); }
    finally { button.disabled = false; }
  }
  function setUser(user) {
    state.user = user;
    document.body.classList.toggle('is-authenticated', !!user);
    $('auth').hidden = !!user;
    $('dashboard').hidden = !user;
    $('logout').hidden = !user;
    if (user) {
      $('greeting').textContent = `Hello, ${user.name}`;
      if (role === 'teacher') $('code').textContent = user.enrollment_code;
    }
  }
  function renderPlan(container, plan) {
    if (!plan || !Array.isArray(plan.days)) return;
    const wrapper = document.createElement('div');
    wrapper.append(text('h4', 'Seven day study plan'));
    for (const day of plan.days) {
      const row = text('div', '', 'day');
      row.append(text('strong', `Day ${day.day}: ${day.focus} · ${day.minutes} min`));
      const list = document.createElement('ul');
      for (const task of day.tasks) list.append(text('li', task));
      row.append(list); wrapper.append(row);
    }
    container.append(wrapper);
  }
  function materialCard(outline, teacher = false) {
    const card = text('article', '', 'outline');
    const title = text('h4', outline.title);
    title.append(text('span', outline.published ? 'Published' : 'Draft', `badge${outline.published ? '' : ' draft'}`));
    card.append(title, text('small', `${outline.subject}${outline.teacher_name ? ` · ${outline.teacher_name}` : ''}`));
    const details = document.createElement('details');
    details.append(text('summary', 'Teacher outline'), text('pre', outline.content));
    card.append(details);
    if (outline.source_text) {
      const source = document.createElement('details');
      source.append(text('summary', 'Teacher-approved source'), text('pre', outline.source_text));
      card.append(source);
    }
    if (outline.notes) {
      const notes = document.createElement('details');
      notes.append(text('summary', 'Revision notes'), text('pre', outline.notes));
      card.append(notes);
      renderPlan(card, outline.study_plan);
      if (outline.generated_by) card.append(text('small', `Generated with ${outline.generated_by}. Review against your course sources.`));
    } else if (!teacher) card.append(text('p', 'Your teacher has not generated study materials for this outline yet.', 'muted'));
    if (teacher) {
      const actions = text('div', '', 'outline-actions');
      const edit = text('button', 'Edit');
      edit.onclick = () => {
        const form = $('outline-form');
        form.elements.title.value = outline.title;
        form.elements.subject.value = outline.subject;
        form.elements.content.value = outline.content;
        form.elements.source_text.value = outline.source_text || '';
        state.editing = outline.id;
        form.querySelector('button[type=submit]').textContent = 'Save changes';
        form.scrollIntoView({behavior: 'smooth'});
      };
      actions.append(edit);
      if (!outline.published) {
        const publish = text('button', 'Publish');
        publish.onclick = () => busy(publish, async () => {
          await api(`/teacher/outlines/${outline.id}/publish`, {method: 'POST'});
          show('Outline published to enrolled students.'); await refreshTeacher();
        });
        actions.append(publish);
      }
      const generate = text('button', outline.notes ? 'Regenerate notes and plan' : 'Generate notes and plan');
      generate.onclick = () => busy(generate, async () => {
        show('Generating study materials. This can take a minute.');
        await api(`/teacher/outlines/${outline.id}/generate`, {method: 'POST'});
        show('Notes and study plan are ready.'); await refreshTeacher();
      });
      actions.append(generate); card.append(actions);
    }
    return card;
  }
  async function refreshTeacher() {
    const [outlines, students] = await Promise.all([api('/teacher/outlines'), api('/teacher/students')]);
    const list = $('outlines'); list.replaceChildren();
    if (!outlines.length) list.append(text('p', 'No outlines yet. Save your first outline to begin.', 'muted'));
    for (const outline of outlines) list.append(materialCard(outline, true));
    const roster = $('students'); roster.replaceChildren();
    roster.append(text('p', students.length ? students.map(s => s.name).join(', ') : 'No students enrolled yet. Share your class code.', 'muted'));
  }
  async function refreshStudent() {
    const [teachers, outlines] = await Promise.all([api('/student/teachers'), api('/student/outlines')]);
    $('teachers').replaceChildren(text('p', teachers.length ? teachers.map(t => t.name).join(', ') : 'Enter your teacher’s code to join a class.', 'muted'));
    const list = $('materials'); list.replaceChildren();
    if (!outlines.length) list.append(text('p', 'Published outlines will appear here once your teacher shares them.', 'muted'));
    for (const outline of outlines) list.append(materialCard(outline));
  }
  async function refresh() { if (role === 'teacher') await refreshTeacher(); else await refreshStudent(); }
  $('auth-toggle').onclick = () => {
    state.mode = state.mode === 'register' ? 'login' : 'register';
    const creating = state.mode === 'register';
    $('name-label').hidden = !creating;
    $('auth-form').elements.name.required = creating;
    $('auth-form').querySelector('button[type=submit]').textContent = creating ? `Create ${role} account` : 'Sign in';
    $('auth-toggle').textContent = creating ? 'Already have an account? Sign in' : 'New here? Create an account';
  };
  $('auth-form').onsubmit = event => {
    event.preventDefault(); const form = event.currentTarget;
    busy(form.querySelector('button[type=submit]'), async () => {
      const body = {email: form.elements.email.value, password: form.elements.password.value};
      if (state.mode === 'register') Object.assign(body, {name: form.elements.name.value, role});
      const user = await api(`/${state.mode}`, {method: 'POST', body: JSON.stringify(body)});
      if (user.role !== role) { location.href = `/${user.role}`; return; }
      setUser(user); await refresh(); show('You are signed in.');
    });
  };
  $('logout').onclick = () => busy($('logout'), async () => {
    await api('/logout', {method: 'POST'}); setUser(null); show('Signed out.');
  });
  if (role === 'teacher') {
    $('copy-code').onclick = async () => {
      try { await navigator.clipboard.writeText(state.user.enrollment_code); show('Enrollment code copied.'); }
      catch { show(`Your code is ${state.user.enrollment_code}`); }
    };
    $('outline-form').onsubmit = event => {
      event.preventDefault(); const form = event.currentTarget;
      busy(form.querySelector('button[type=submit]'), async () => {
        const body = JSON.stringify({title: form.elements.title.value, subject: form.elements.subject.value, content: form.elements.content.value, source_text: form.elements.source_text.value});
        const path = state.editing ? `/teacher/outlines/${state.editing}` : '/teacher/outlines';
        await api(path, {method: state.editing ? 'PUT' : 'POST', body});
        form.reset(); state.editing = null;
        form.querySelector('button[type=submit]').textContent = 'Save outline';
        show('Outline saved. Publish it when ready.'); await refreshTeacher();
      });
    };
  } else {
    $('enroll-form').onsubmit = event => {
      event.preventDefault(); const form = event.currentTarget;
      busy(form.querySelector('button[type=submit]'), async () => {
        const teacher = await api('/student/enroll', {method: 'POST', body: JSON.stringify({code: form.elements.code.value})});
        form.reset(); show(`Joined ${teacher.name}'s class.`); await refreshStudent();
      });
    };
  }
  api('/me').then(user => {
    if (user.role !== role) { location.href = `/${user.role}`; return; }
    setUser(user); return refresh();
  }).catch(error => { if (!error.message.includes('Sign in') && !error.message.includes('Session expired')) show(error.message, true); });
})();
