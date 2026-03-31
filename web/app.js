const sentCount = document.getElementById("sentCount");
const pendingCount = document.getElementById("pendingCount");
const failedCount = document.getElementById("failedCount");
const seenCount = document.getElementById("seenCount");
const runStatus = document.getElementById("runStatus");
const itemsEl = document.getElementById("items");
const statusFilter = document.getElementById("statusFilter");
const refreshBtn = document.getElementById("refreshBtn");
const actionButtons = Array.from(document.querySelectorAll("button[data-mode]"));

const aiForm = document.getElementById("aiForm");
const aiSubmitBtn = document.getElementById("aiSubmitBtn");
const aiStatus = document.getElementById("aiStatus");
const aiResult = document.getElementById("aiResult");

function fmtTs(sec) {
  if (!sec) return "-";
  return new Date(sec * 1000).toLocaleString();
}

function esc(text) {
  const s = String(text || "");
  return s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function setRunningUi(running) {
  actionButtons.forEach((b) => (b.disabled = running));
}

async function fetchSummary() {
  const res = await fetch("/api/summary");
  const j = await res.json();
  const d = j.data || {};
  sentCount.textContent = d.sent ?? "-";
  pendingCount.textContent = d.pending ?? "-";
  failedCount.textContent = d.failed ?? "-";
  seenCount.textContent = d.seen ?? "-";

  const run = j.run || {};
  runStatus.className = "run-status";
  if (run.running) {
    runStatus.classList.add("running");
    runStatus.textContent = `运行中：${run.last_mode || "full"}（开始于 ${fmtTs(run.last_started_at)}）`;
  } else if (run.last_ok === false) {
    runStatus.classList.add("error");
    runStatus.textContent = `上次失败：${run.last_mode || "-"}，${run.last_error || "unknown"}`;
  } else if (run.last_ok === true) {
    runStatus.textContent = `上次完成：${run.last_mode || "-"}，耗时 ${run.last_duration_sec || 0}s`;
  } else {
    runStatus.textContent = "未运行";
  }
  setRunningUi(Boolean(run.running));
}

async function fetchItems() {
  const status = statusFilter.value;
  const res = await fetch(`/api/items?status=${encodeURIComponent(status)}&limit=20`);
  const j = await res.json();
  const rows = j.data || [];
  itemsEl.innerHTML = "";
  if (rows.length === 0) {
    const li = document.createElement("li");
    li.textContent = "暂无记录";
    itemsEl.appendChild(li);
    return;
  }

  for (const r of rows) {
    const li = document.createElement("li");
    const title = r.title || "(无标题)";
    const meta = `${r.source_name || "-"} | attempts=${r.attempts} | ${r.updated_at || "-"}`;
    li.innerHTML = `
      <div><a href="${r.url || "#"}" target="_blank" rel="noreferrer">${esc(title)}</a></div>
      <div class="meta">${esc(meta)}</div>
    `;
    itemsEl.appendChild(li);
  }
}

async function triggerRun(mode) {
  const res = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  const j = await res.json();
  if (!j.ok) {
    runStatus.className = "run-status error";
    runStatus.textContent = `启动失败：${j.error || "unknown"}`;
    return;
  }
  runStatus.className = "run-status running";
  runStatus.textContent = `已启动：${mode}`;
  setRunningUi(true);
  await fetchSummary();
}

actionButtons.forEach((btn) => {
  btn.addEventListener("click", () => triggerRun(btn.dataset.mode));
});

refreshBtn.addEventListener("click", async () => {
  await fetchSummary();
  await fetchItems();
});

statusFilter.addEventListener("change", fetchItems);

function renderAiResult(payload) {
  const article = payload?.data?.article || {};
  const keywords = Array.isArray(article.keywords) ? article.keywords.join(", ") : "";
  const gh = payload?.saved_github || {};
  const ghMsg = gh.ok
    ? `已存入 GitHub: ${gh.repo}/${gh.path}`
    : gh.skipped
      ? `GitHub 未启用: ${gh.reason}`
      : `GitHub 存储失败: ${gh.error || "unknown"}`;

  aiResult.innerHTML = `
    <h3>${esc(article.title_cn || "（无标题）")}</h3>
    <p><strong>摘要：</strong>${esc(article.summary_cn || "")}</p>
    <p><strong>关键词：</strong>${esc(keywords)}</p>
    <div class="article-body">${esc(article.article_cn || "").replaceAll("\n", "<br/>")}</div>
    <div class="meta">本地保存：${esc(payload.saved_local || "-")}</div>
    <div class="meta">${esc(ghMsg)}</div>
  `;
}

aiForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = {
    title: document.getElementById("aiTitle").value.trim(),
    source: document.getElementById("aiSource").value.trim(),
    url: document.getElementById("aiUrl").value.trim(),
    prompt: document.getElementById("aiPrompt").value.trim(),
    content: document.getElementById("aiContent").value.trim(),
    audience: document.getElementById("aiAudience").value.trim(),
    tone: document.getElementById("aiTone").value.trim(),
  };

  if (!data.content) {
    aiStatus.className = "run-status error";
    aiStatus.textContent = "请先输入原始内容";
    return;
  }

  aiSubmitBtn.disabled = true;
  aiStatus.className = "run-status running";
  aiStatus.textContent = "AI 处理中，请稍候...";
  aiResult.innerHTML = "";

  try {
    const res = await fetch("/api/ai/clean", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const j = await res.json();
    if (!j.ok) {
      aiStatus.className = "run-status error";
      aiStatus.textContent = `处理失败：${j.error || "unknown"}`;
      return;
    }
    aiStatus.className = "run-status";
    aiStatus.textContent = "处理成功";
    renderAiResult(j);
  } catch (err) {
    aiStatus.className = "run-status error";
    aiStatus.textContent = `请求失败：${String(err)}`;
  } finally {
    aiSubmitBtn.disabled = false;
  }
});

async function boot() {
  await fetchSummary();
  await fetchItems();
  setInterval(fetchSummary, 3000);
}

boot().catch((err) => {
  runStatus.className = "run-status error";
  runStatus.textContent = `加载失败：${String(err)}`;
});
