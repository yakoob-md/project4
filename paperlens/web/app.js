const form = document.querySelector('form');
const report = document.querySelector('article');
const statusLine = document.querySelector('#status');
let parent = '';
const add = (root, tag, value) => { const el = document.createElement(tag); el.textContent = value; root.append(el); return el; };
form.cutoff.value = new Date().toISOString().slice(0, 10);

function mode() {
  const idea = form.mode.value === 'idea';
  document.querySelector('#upload').hidden = idea;
  form.pdf.disabled = idea;
  document.querySelector('#context').firstChild.textContent = idea ? 'Idea and research constraints' : 'Paper text (or upload a PDF)';
}
form.mode.onchange = () => { parent = ''; mode(); };

function show(run) {
  report.replaceChildren(); add(report, 'h2', run.question); add(report, 'p', run.status);
  run.warnings.forEach((warning) => add(report, 'p', warning));
  for (const [name, review] of Object.entries(run.reviews)) {
    add(report, 'h3', name);
    for (const finding of review.findings) { add(report, 'p', finding.assessment); add(report, 'blockquote', `${finding.quote} [${finding.source}]`); add(report, 'p', finding.action); }
    review.unknowns.forEach((unknown) => add(report, 'p', unknown));
  }
  if (run.critique?.length) {
    add(report, 'h3', 'Critique and revisions');
    for (const item of run.critique) { const d = add(report, 'details', ''); add(d, 'summary', `${item.challenge.owner} · ${item.response.decision}`); add(d, 'p', item.original.assessment); add(d, 'p', item.challenge.concern); add(d, 'p', item.response.reason); add(d, 'p', `Closure: ${item.disposition ?? 'unresolved'}`); }
  }
  for (const source of run.sources) { const d = add(report, 'details', ''); add(d, 'summary', `${source.id} · ${source.title} · ${source.locator}`); add(d, 'p', source.text); if (source.url) { const a = add(d, 'a', 'Open source'); a.href = source.url; a.target = '_blank'; a.rel = 'noopener noreferrer'; } }
  for (const [label, suffix] of [['JSON', ''], ['Markdown', '/markdown']]) { const a = add(report, 'a', label); a.href = `/runs/${run.id}${suffix}`; a.download = `paperlens.${suffix ? 'md' : 'json'}`; }
  if (run.mode === 'idea') add(report, 'button', 'Refine and rerun').onclick = () => { form.mode.value = 'idea'; mode(); form.text.value = run.input_text; form.question.value = run.question; form.cutoff.value = run.cutoff; parent = run.id; form.question.focus(); };
}

async function history() { const list = document.querySelector('#historyList'); list.replaceChildren(); for (const run of await (await fetch('/runs')).json()) add(list, 'button', run.question).onclick = async () => show(await (await fetch(`/runs/${run.id}`)).json()); }
form.onsubmit = async (event) => { event.preventDefault(); const body = new FormData(form); if (!form.pdf.files.length) body.delete('pdf'); if (parent) body.set('parent', parent); const button = form.querySelector('button'); button.disabled = true; statusLine.textContent = 'Retrieving evidence and preparing analysis…'; try { const response = await fetch('/runs', {method: 'POST', body}); const data = await response.json(); if (!response.ok) throw Error(JSON.stringify(data.detail)); show(data); parent = ''; await history(); statusLine.textContent = 'Run saved.'; } catch (error) { statusLine.textContent = error.message; } finally { button.disabled = false; } };
mode(); history();
