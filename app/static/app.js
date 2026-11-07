let mode = 'balanced';
const $ = id => document.getElementById(id);
document.querySelectorAll('.mode').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('.mode').forEach(item => item.classList.remove('active'));
  button.classList.add('active');
  mode = button.dataset.mode;
}));

function requestBody() {
  const prompt = $('prompt').value.trim();
  if (prompt.length < 3) throw new Error('Please enter a descriptive prompt.');
  const seedValue = $('seed').value;
  return {
    prompt,
    seed: seedValue === '' ? null : Number(seedValue),
    resolution: Number($('resolution').value),
    classical_enhance: $('enhance').checked,
  };
}

async function postJson(path, body) {
  const response = await fetch(path, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'Request failed.');
  return data;
}

function showImage(container, data) {
  const img = document.createElement('img');
  img.alt = 'Generated image';
  img.src = `data:${data.mime_type};base64,${data.image}`;
  container.replaceChildren(img);
}

function showMetrics(data) {
  $('latency').textContent = `${(data.generation_ms / 1000).toFixed(2)}s`;
  $('clip').textContent = data.clip_score === null ? 'N/A' : data.clip_score;
  $('memory').textContent = data.peak_gpu_memory_mb === null ? 'CPU' : `${data.peak_gpu_memory_mb} MB`;
  $('ram').textContent = `${data.process_rss_after_mb} MB`;
  $('steps').textContent = data.steps;
  $('size').textContent = `${data.resolution} × ${data.resolution}`;
  $('metrics').classList.remove('hidden');
  const reason = $('autoReason');
  if (data.auto_reason) {
    reason.textContent = `AUTO selected ${data.mode.toUpperCase()} · ${data.resolution} × ${data.resolution}. ${data.auto_reason}`;
    reason.classList.remove('hidden');
  } else {
    reason.classList.add('hidden');
  }
  $('download').href = `data:${data.mime_type};base64,${data.image}`;
  $('download').classList.remove('hidden');
}

$('generate').addEventListener('click', async () => {
  const button = $('generate');
  try {
    const body = {...requestBody(), mode};
    button.disabled = true;
    $('compare').disabled = true;
    $('status').textContent = 'RUNNING';
    $('canvas').innerHTML = '<div class="placeholder"><div class="spark">✳</div><b>Creating your image…</b><span>First run may take longer while models load.</span></div>';
    $('metrics').classList.add('hidden');
    $('download').classList.add('hidden');
    const data = await postJson('/generate', body);
    showImage($('canvas'), data);
    showMetrics(data);
    $('status').textContent = 'COMPLETE';
  } catch (error) {
    const message = document.createElement('span');
    message.textContent = error.message;
    $('canvas').replaceChildren(message);
    $('status').textContent = 'ERROR';
  } finally {
    button.disabled = false;
    $('compare').disabled = false;
  }
});

function makeComparisonCard(result) {
  const card = document.createElement('article');
  card.className = 'comparison-card';
  const title = document.createElement('h3');
  title.textContent = result.label;
  const image = document.createElement('img');
  image.alt = `${result.label} generated result`;
  image.src = `data:${result.mime_type};base64,${result.image}`;
  const details = document.createElement('dl');
  const rows = [
    ['Time', `${(result.generation_ms / 1000).toFixed(2)} s`],
    ['CLIP cosine', result.clip_score ?? 'N/A'],
    ['GPU peak', result.peak_gpu_memory_mb === null ? 'N/A' : `${result.peak_gpu_memory_mb} MB`],
    ['Process RAM after', `${result.process_rss_after_mb} MB`],
    ['Steps / size', `${result.steps} / ${result.resolution}²`],
  ];
  for (const [name, value] of rows) {
    const term = document.createElement('dt'); term.textContent = name;
    const description = document.createElement('dd'); description.textContent = value;
    details.append(term, description);
  }
  if (result.auto_reason) {
    const reason = document.createElement('p'); reason.className = 'card-reason'; reason.textContent = result.auto_reason;
    card.append(title, image, details, reason);
  } else card.append(title, image, details);
  return card;
}

$('compare').addEventListener('click', async () => {
  const button = $('compare');
  try {
    const body = {...requestBody(), mode: 'balanced'};
    button.disabled = true;
    $('generate').disabled = true;
    $('status').textContent = 'COMPARING';
    $('comparison').classList.remove('hidden');
    $('comparisonCards').textContent = 'Running three generations with the same prompt and seed…';
    const data = await postJson('/compare', body);
    const cards = data.results.map(makeComparisonCard);
    $('comparisonCards').replaceChildren(...cards);
    const report = {
      prompt: data.prompt, seed: data.seed, requested_resolution: data.requested_resolution,
      same_prompt_and_seed: data.same_prompt_and_seed,
      results: data.results.map(({image, ...metrics}) => metrics),
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], {type: 'application/json'});
    $('reportDownload').href = URL.createObjectURL(blob);
    $('status').textContent = 'COMPLETE';
  } catch (error) {
    $('comparisonCards').textContent = error.message;
    $('status').textContent = 'ERROR';
  } finally {
    button.disabled = false;
    $('generate').disabled = false;
  }
});
