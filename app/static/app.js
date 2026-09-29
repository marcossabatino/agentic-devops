const form = document.querySelector('#run-form');
const status = document.querySelector('#request-status');
const submit = document.querySelector('#submit');
const approve = document.querySelector('#approve');
const setText = (id, value) => { document.getElementById(id).textContent = value; };
let currentRun;

function showRun(run) {
  currentRun = run;
  setText('summary', run.summary);
  setText('run-status', run.status);
  setText('outcome', run.outcome ?? 'unknown');
  setText('duration', `${run.duration_ms} ms`);
  setText('started', run.started_at);
  setText('run-id', run.run_id);
  setText('revision', run.revision);
  setText('trace-id', run.trace_id ?? 'Not available in this mode');
  setText('raw-result', JSON.stringify(run, null, 2));
  const steps = document.querySelector('#steps');
  steps.replaceChildren();
  for (const step of run.steps) {
    const item = document.createElement('li');
    const title = document.createElement('strong');
    title.textContent = `${step.tool} · ${step.status} · ${step.duration_ms} ms`;
    const record = document.createElement('pre');
    record.textContent = JSON.stringify({ arguments: step.arguments, result: step.result }, null, 2);
    item.append(title, record);
    steps.append(item);
  }
  const error = document.querySelector('#run-error');
  error.hidden = !run.error;
  error.textContent = run.error ? `Execution error: ${run.error}` : '';
  document.querySelector('#approval-panel').hidden = run.status !== 'awaiting_approval';
  setText('approval-details', JSON.stringify(run.pending_approval ?? {}, null, 2));
  document.querySelector('#result').hidden = false;
}

async function request(path, payload) {
  const headers = { 'Content-Type': 'application/json' };
  const token = document.querySelector('#user-token').value;
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, {
    method: payload ? 'POST' : 'GET', headers,
    body: payload ? JSON.stringify(payload) : undefined,
    signal: AbortSignal.timeout(10000),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error ?? 'Request failed.');
  return body;
}

async function follow(run) {
  const until = Date.now() + 45000;
  showRun(run);
  // Polling is bounded independently of the server's durable execution deadline.
  while (['queued', 'running'].includes(run.status)) {
    if (Date.now() >= until) throw new Error(`Polling stopped. Retrieve run ${run.run_id} through the API.`);
    await new Promise((resolve) => setTimeout(resolve, 300));
    run = await request(`/api/runs/${run.run_id}`);
    showRun(run);
  }
  status.textContent = run.status === 'completed' ? 'Diagnosis completed.'
    : run.status === 'awaiting_approval' ? 'Waiting for your explicit approval.'
      : 'Diagnosis failed. Inspect the execution error below.';
}

async function perform(action) {
  submit.disabled = true;
  approve.disabled = true;
  status.className = '';
  status.textContent = 'Running the simulated diagnosis…';
  try {
    await follow(await action());
  } catch (error) {
    status.className = 'error';
    status.textContent = `Unable to run the diagnosis: ${error.message}`;
  } finally {
    submit.disabled = false;
    approve.disabled = false;
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  document.querySelector('#result').hidden = true;
  await perform(() => request('/api/runs', {
    question: document.querySelector('#question').value,
    scenario: document.querySelector('#scenario').value,
  }));
});

approve.addEventListener('click', async () => {
  if (currentRun?.status !== 'awaiting_approval') return;
  await perform(() => request(`/api/runs/${currentRun.run_id}/approval`, currentRun.pending_approval));
});

fetch('/api/info')
  .then((response) => { if (!response.ok) throw new Error('Unavailable'); return response.json(); })
  .then((info) => {
    setText('build-info', `${info.mode} · Source ${info.revision}`);
    const durable = info.storage === 'postgresql';
    document.querySelector('#credentials').hidden = !durable;
    setText('storage-info', durable ? 'PostgreSQL history · Runs survive application restarts.'
      : 'In-memory history: latest 100 runs · Restarting the app clears history.');
    const names = { healthy: 'Healthy service', 'orders-errors': 'Service returning errors',
      'restart-required': 'Service needs a simulated restart', 'tool-timeout': 'Tool unavailable / timeout',
      'step-limit': 'Repeated tool requests / step limit', 'deadline-exceeded': 'Total deadline exceeded' };
    const select = document.querySelector('#scenario');
    select.replaceChildren(...info.scenarios.map((scenario) => {
      const option = document.createElement('option');
      option.value = scenario;
      option.textContent = names[scenario] ?? scenario;
      return option;
    }));
    select.value = info.active_scenario ?? 'healthy';
  })
  .catch(() => setText('build-info', 'Build information unavailable.'));
