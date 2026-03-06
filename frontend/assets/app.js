const state = {
  draft: null,
  lastParserBackend: null,
};

const el = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  let payload = null;
  const text = await response.text();
  if (text) {
    payload = JSON.parse(text);
  }

  if (!response.ok) {
    const detail = payload?.detail || text || `Request failed: ${response.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

function toast(message) {
  const node = el("toast");
  node.textContent = message;
  node.classList.remove("hidden");
  window.clearTimeout(window.__toastTimer);
  window.__toastTimer = window.setTimeout(() => node.classList.add("hidden"), 3000);
}

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function renderList(targetId, items, renderer, emptyText) {
  const target = el(targetId);
  target.innerHTML = "";
  if (!items || items.length === 0) {
    target.innerHTML = `<div class="list-item"><span>${emptyText}</span></div>`;
    return;
  }
  for (const item of items) {
    const wrapper = document.createElement("div");
    wrapper.className = "list-item";
    wrapper.innerHTML = renderer(item);
    target.appendChild(wrapper);
  }
}

async function loadHealth() {
  const health = await api("/health");
  el("health-build").textContent = health.build_stage;
  el("health-db").textContent = health.database_exists ? "已连接" : "未初始化";
  el("health-scheduler").textContent = health.analytics_scheduler_enabled ? "开启" : "关闭";
}

async function loadEvents() {
  const events = await api("/events");
  renderList(
    "events-list",
    events.slice(0, 8),
    (item) => `
      <strong>${item.title}</strong>
      <div>${item.event_type || "unknown"} · body ${item.body_delta >= 0 ? "+" : ""}${item.body_delta} · mind ${item.mind_delta >= 0 ? "+" : ""}${item.mind_delta}</div>
      <div>${item.occurred_at}</div>
    `,
    "暂无事件"
  );
}

async function loadKeyNodes() {
  const nodes = await api("/key-nodes");
  const select = el("key-node-id");
  const current = select.value;
  select.innerHTML = nodes
    .map((node) => `<option value="${node.id}">${node.name} (${Math.round((node.progress || 0) * 100)}%)</option>`)
    .join("");
  if (current) {
    select.value = current;
  }

  renderList(
    "key-nodes-list",
    nodes,
    (item) => `
      <strong>${item.name}</strong>
      <div>${item.node_type} · status ${item.status}</div>
      <div>progress ${(item.progress * 100).toFixed(1)}%</div>
    `,
    "暂无关键节点"
  );
}

async function loadReviewAndSnapshot() {
  const [review, snapshot] = await Promise.all([
    api("/weekly-review").catch(() => null),
    api("/snapshot").catch(() => null),
  ]);
  el("weekly-review-output").textContent = review?.markdown_content || "暂无周复盘";
  el("snapshot-output").textContent = snapshot ? pretty(snapshot) : "暂无快照";
}

async function loadAnalytics() {
  const [insights, scheduler] = await Promise.all([
    api("/analytics/insights/latest"),
    api("/analytics/scheduler/status"),
  ]);

  el("analytics-run-output").textContent = insights.run ? pretty(insights.run) : "暂无批次";
  el("scheduler-output").textContent = pretty(scheduler);

  renderList(
    "energy-rules-list",
    insights.energy_rules || [],
    (item) => `
      <strong>${item.event_type}</strong>
      <div>samples ${item.sample_count} · confidence <span class="pill">${item.confidence}</span></div>
      <div>body ${Number(item.expected_body_delta).toFixed(2)} · mind ${Number(item.expected_mind_delta).toFixed(2)}</div>
    `,
    "暂无 energy rules"
  );

  renderList(
    "progress-rules-list",
    insights.progress_rules || [],
    (item) => `
      <strong>${item.event_type} -> ${item.node_type}</strong>
      <div>samples ${item.sample_count} · confidence <span class="pill">${item.confidence}</span></div>
      <div>progress ${Number(item.expected_progress_delta).toFixed(4)}</div>
    `,
    "暂无 progress rules"
  );

  renderSuggestions(insights.pending_suggestions || []);
}

function renderSuggestions(suggestions) {
  const target = el("suggestions-list");
  target.innerHTML = "";
  if (!suggestions.length) {
    target.innerHTML = `<div class="list-item"><span>暂无待审批建议</span></div>`;
    return;
  }

  for (const item of suggestions) {
    const wrapper = document.createElement("div");
    wrapper.className = "list-item";
    const payload = item.suggested_payload_json ? JSON.parse(item.suggested_payload_json) : {};
    wrapper.innerHTML = `
      <strong>${item.rule_type} · ${item.target_key}</strong>
      <div class="pill">${item.status}</div>
      <div class="suggestion-editor">
        <select data-role="status">
          <option value="approved">approved</option>
          <option value="edited" selected>edited</option>
          <option value="rejected">rejected</option>
        </select>
        <textarea data-role="payload">${pretty(payload)}</textarea>
        <input data-role="note" type="text" placeholder="reviewer note">
        <button data-action="review" data-id="${item.id}">提交审批</button>
      </div>
    `;
    wrapper.querySelector('[data-action="review"]').addEventListener("click", async () => {
      const status = wrapper.querySelector('[data-role="status"]').value;
      const note = wrapper.querySelector('[data-role="note"]').value;
      let approvedPayload = null;
      if (status !== "rejected") {
        approvedPayload = JSON.parse(wrapper.querySelector('[data-role="payload"]').value);
      }
      await api(`/analytics/suggestions/${item.id}/review`, {
        method: "POST",
        body: JSON.stringify({
          approval_status: status,
          approved_payload_json: approvedPayload,
          reviewer_note: note || null,
        }),
      });
      toast("建议审批已保存");
      await loadAnalytics();
    });
    target.appendChild(wrapper);
  }
}

async function refreshAll() {
  await Promise.all([loadHealth(), loadEvents(), loadKeyNodes(), loadReviewAndSnapshot(), loadAnalytics()]);
}

el("parse-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    text: el("nl-text").value,
    occurred_at_hint: el("nl-occurred-at").value || null,
  };
  const result = await api("/events/parse", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.draft = result.structured_event;
  state.lastParserBackend = result.parser_backend;
  el("draft-json").value = pretty(result.structured_event);
  el("confirm-draft").disabled = false;
  toast("事件草稿已生成");
});

el("confirm-draft").addEventListener("click", async () => {
  const structuredEvent = JSON.parse(el("draft-json").value);
  await api("/events/confirm", {
    method: "POST",
    body: JSON.stringify({
      structured_event: structuredEvent,
      parser_backend: state.lastParserBackend,
      original_text: el("nl-text").value || null,
    }),
  });
  toast("事件已确认写库");
  await refreshAll();
});

el("create-direct-event").addEventListener("click", async () => {
  await api("/events", {
    method: "POST",
    body: JSON.stringify({
      title: "Quick capture",
      description: "Manual quick capture from the dashboard",
      event_type: "note",
      body_delta: 0,
      mind_delta: 1,
    }),
  });
  toast("示例事件已写入");
  await refreshAll();
});

el("key-node-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {};
  const progress = el("key-node-progress").value;
  const eventId = el("key-node-event-id").value;
  const reason = el("key-node-reason").value;
  if (progress) payload.progress = Number(progress);
  if (eventId) payload.source_event_id = Number(eventId);
  if (reason) payload.reason = reason;
  await api(`/key-nodes/${el("key-node-id").value}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  toast("节点已更新");
  await refreshAll();
});

el("generate-review").addEventListener("click", async () => {
  await api("/weekly-review/generate", {
    method: "POST",
    body: JSON.stringify({}),
  });
  toast("周复盘已生成");
  await loadReviewAndSnapshot();
});

el("generate-snapshot").addEventListener("click", async () => {
  await api("/snapshot/generate", {
    method: "POST",
    body: JSON.stringify({}),
  });
  toast("快照已生成");
  await loadReviewAndSnapshot();
});

el("run-analytics").addEventListener("click", async () => {
  await api("/analytics/run", {
    method: "POST",
    body: JSON.stringify({}),
  });
  toast("分析批次已生成");
  await loadAnalytics();
});

el("refresh-analytics").addEventListener("click", loadAnalytics);
el("refresh-all").addEventListener("click", refreshAll);

refreshAll().catch((error) => {
  console.error(error);
  toast(error.message);
});
