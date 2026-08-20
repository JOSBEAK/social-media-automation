const state = { batches: { instagram: [], twitter: [] }, toastTimer: null };

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { message = (await response.json()).detail || message; } catch (_) {}
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
}

function toast(message, error = false) {
  const element = document.querySelector("#toast");
  element.textContent = message;
  element.className = `toast show${error ? " error" : ""}`;
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => { element.className = "toast"; }, 3500);
}

function setBusy(form, busy) {
  const button = form.querySelector("button[type='submit']");
  button.disabled = busy;
  if (!button.dataset.label) button.dataset.label = button.textContent;
  button.textContent = busy ? "Working…" : button.dataset.label;
}

async function loadBatches(platform) {
  const batches = await api(`/api/v1/platforms/${platform}/batches`);
  state.batches[platform] = batches;
  const card = document.querySelector(`[data-platform="${platform}"]`);
  card.querySelector(".batch-count").textContent = batches.length;
  const list = card.querySelector(".batch-list");
  const select = card.querySelector(".job-batch");

  list.innerHTML = batches.length ? batches.map(batch => `
    <div class="batch-item">
      <div><strong>${escapeHtml(batch.name)}</strong><small>${escapeHtml(batch.filename)}</small></div>
      <span class="account-badge">${batch.account_count} accounts</span>
      <button class="delete-batch" type="button" data-id="${batch.id}" aria-label="Delete ${escapeHtml(batch.name)}">×</button>
    </div>`).join("") : '<div class="empty-batches">No batches uploaded in this section.</div>';

  select.innerHTML = batches.length
    ? '<option value="">Choose a batch</option>' + batches.map(batch => `<option value="${batch.id}">${escapeHtml(batch.name)} · ${batch.account_count}</option>`).join("")
    : '<option value="">Upload a batch first</option>';

  list.querySelectorAll(".delete-batch").forEach(button => button.addEventListener("click", async () => {
    if (!window.confirm("Delete this unused account batch?")) return;
    try {
      await api(`/api/v1/platforms/${platform}/batches/${button.dataset.id}`, { method: "DELETE" });
      await Promise.all([loadBatches(platform), loadStats()]);
      toast("Account batch deleted");
    } catch (error) { toast(error.message, true); }
  }));
}

async function loadStats() {
  const stats = await api("/api/v1/health");
  document.querySelector("#metric-accounts").textContent = stats.accounts;
  document.querySelector("#metric-queued").textContent = stats.queued;
  document.querySelector("#metric-running").textContent = stats.running;
  document.querySelector("#metric-completed").textContent = stats.completed;
}

function renderJobs(jobs) {
  const body = document.querySelector("#jobs-body");
  if (!jobs.length) {
    body.innerHTML = '<tr><td class="empty-row" colspan="6">No jobs yet. Your first queued job will appear here.</td></tr>';
    return;
  }
  body.innerHTML = jobs.map(job => {
    const percent = job.total ? Math.round((job.completed / job.total) * 100) : 0;
    const created = new Date(job.created_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
    const result = job.status === "failed" ? escapeHtml(job.error || "Job failed") : `${job.succeeded} passed · ${job.failed} failed`;
    return `<tr>
      <td><span class="job-id">${job.id.slice(0, 8)}</span><br><strong>${escapeHtml(job.action)}</strong></td>
      <td>${job.platform === "twitter" ? "X / Twitter" : "Instagram"}</td>
      <td>${escapeHtml(job.batch_name)}</td>
      <td><div class="progress"><i style="width:${percent}%"></i></div><span class="progress-label">${job.completed} of ${job.total}</span></td>
      <td><span class="status ${job.status}">${job.status}</span><br><span class="progress-label">${result}</span></td>
      <td>${created}</td>
    </tr>`;
  }).join("");
}

async function loadJobs() {
  try { renderJobs(await api("/api/v1/jobs?limit=50")); } catch (error) { toast(error.message, true); }
}

document.querySelectorAll(".platform-card").forEach(card => {
  const platform = card.dataset.platform;
  const uploadForm = card.querySelector(".upload-form");
  const fileInput = card.querySelector(".csv-file");
  const dropZone = card.querySelector(".drop-zone");
  const dropTitle = card.querySelector(".drop-title");

  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    dropZone.classList.toggle("has-file", Boolean(file));
    dropTitle.textContent = file ? file.name : "Drop an account CSV here";
  });

  uploadForm.addEventListener("submit", async event => {
    event.preventDefault();
    const file = fileInput.files[0];
    if (!file) return toast("Choose a CSV file first", true);
    const data = new FormData();
    data.append("file", file);
    const name = card.querySelector(".batch-name").value.trim();
    if (name) data.append("name", name);
    setBusy(uploadForm, true);
    try {
      const batch = await api(`/api/v1/platforms/${platform}/batches`, { method: "POST", body: data });
      uploadForm.reset();
      dropZone.classList.remove("has-file");
      dropTitle.textContent = "Drop an account CSV here";
      await Promise.all([loadBatches(platform), loadStats()]);
      toast(`${batch.account_count} accounts saved as “${batch.name}”`);
    } catch (error) { toast(error.message, true); }
    finally { setBusy(uploadForm, false); }
  });

  const jobForm = card.querySelector(".job-form");
  const action = card.querySelector(".job-action");
  const commentField = card.querySelector(".comment-field");
  action.addEventListener("change", () => {
    commentField.classList.toggle("hidden", !["comment", "reply"].includes(action.value));
  });

  jobForm.addEventListener("submit", async event => {
    event.preventDefault();
    const payload = {
      batch_id: card.querySelector(".job-batch").value,
      action: action.value,
      target_url: card.querySelector(".job-url").value.trim(),
      comment_text: card.querySelector(".job-comment").value.trim() || null,
    };
    if (!payload.batch_id) return toast("Choose an account batch", true);
    setBusy(jobForm, true);
    try {
      const job = await api("/api/v1/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      jobForm.querySelector(".job-url").value = "";
      jobForm.querySelector(".job-comment").value = "";
      await Promise.all([loadJobs(), loadStats()]);
      toast(`Job ${job.id.slice(0, 8)} queued. Workers will pick it up.`);
    } catch (error) { toast(error.message, true); }
    finally { setBusy(jobForm, false); }
  });
});

document.querySelector("#download-template").addEventListener("click", () => {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob(["username,password\nexample_user,replace-me\n"], { type: "text/csv" }));
  link.download = "accounts-template.csv";
  link.click();
  URL.revokeObjectURL(link.href);
});
document.querySelector("#refresh-jobs").addEventListener("click", () => Promise.all([loadJobs(), loadStats()]));

Promise.all([loadBatches("instagram"), loadBatches("twitter"), loadJobs(), loadStats()])
  .catch(error => toast(error.message, true));
setInterval(() => Promise.all([loadJobs(), loadStats()]), 2500);
