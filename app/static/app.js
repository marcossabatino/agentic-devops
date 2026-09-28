const form = document.querySelector('#run-form');
const status = document.querySelector('#request-status');
const submit = document.querySelector('#submit');
const setText = (id, value) => { document.getElementById(id).textContent = value; };

function showRun(run) {
  setText('summary', run.summary);
  setText('run-status', run.status);
  setText('outcome', run.outcome ?? 'unknown');
  setText('duration', `${run.duration_ms} ms`);
  setText('started', run.started_at);
  setText('run-id', run.run_id);
  setText('revision', run.revision);
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
  document.querySelector('#result').hidden = false;
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  submit.disabled = true;
  status.className = '';
  status.textContent = 'Running the simulated diagnosis…';
  document.querySelector('#result').hidden = true;
  try {
    const response = await fetch('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: document.querySelector('#question').value,
        scenario: document.querySelector('#scenario').value,
      }),
      signal: AbortSignal.timeout(10000),
    });
    const run = await response.json();
    if (!response.ok) throw new Error(run.error ?? 'Request failed.');
    showRun(run);
    status.textContent = run.status === 'completed' ? 'Diagnosis completed.' : 'Diagnosis failed. Inspect the execution error below.';
  } catch (error) {
    status.className = 'error';
    status.textContent = `Unable to run the diagnosis: ${error.message}`;
  } finally {
    submit.disabled = false;
  }
});

fetch('/api/info')
  .then((response) => { if (!response.ok) throw new Error('Unavailable'); return response.json(); })
  .then((info) => setText('build-info', `${info.mode} · Source ${info.revision}`))
  .catch(() => setText('build-info', 'Build information unavailable.'));
