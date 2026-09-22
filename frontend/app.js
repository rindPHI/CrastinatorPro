const API_BASE = "/api";

let users = [];

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: options.body ? { "Content-Type": "application/json" } : undefined,
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch (_) {
      /* keine JSON-Antwort */
    }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

function userName(userId) {
  const user = users.find((u) => u.id === userId);
  return user ? user.name : "—";
}

function priorityLabel(priority) {
  return { low: "niedrig", medium: "mittel", high: "hoch" }[priority] || priority;
}

async function loadUsers() {
  users = await apiFetch("/users");
  const selects = [
    document.getElementById("task-assignee"),
    document.getElementById("filter-assignee"),
    document.getElementById("ask-user"),
  ];
  for (const select of selects) {
    for (const user of users) {
      const option = document.createElement("option");
      option.value = String(user.id);
      option.textContent = user.name;
      select.appendChild(option);
    }
  }
}

function buildTaskListQuery() {
  const params = new URLSearchParams();
  const sortBy = document.getElementById("sort-by").value;
  const order = document.getElementById("sort-order").value;
  const assignee = document.getElementById("filter-assignee").value;
  const completed = document.getElementById("filter-completed").value;

  if (sortBy) params.set("sortBy", sortBy);
  if (order) params.set("order", order);
  if (assignee) params.set("assigneeUserId", assignee);
  if (completed) params.set("completed", completed);
  return params.toString();
}

function renderTaskRow(task) {
  const tr = document.createElement("tr");

  const titleTd = document.createElement("td");
  titleTd.textContent = task.title;
  if (task.completed) titleTd.classList.add("completed-row");
  tr.appendChild(titleTd);

  const descTd = document.createElement("td");
  descTd.textContent = task.description || "";
  tr.appendChild(descTd);

  const dueTd = document.createElement("td");
  dueTd.textContent = task.dueDate || "—";
  tr.appendChild(dueTd);

  const prioTd = document.createElement("td");
  prioTd.textContent = priorityLabel(task.priority);
  prioTd.classList.add(`priority-${task.priority}`);
  tr.appendChild(prioTd);

  const assigneeTd = document.createElement("td");
  assigneeTd.textContent = task.assigneeUserId ? userName(task.assigneeUserId) : "—";
  tr.appendChild(assigneeTd);

  const statusTd = document.createElement("td");
  statusTd.textContent = task.completed ? "erledigt" : "offen";
  tr.appendChild(statusTd);

  const actionsTd = document.createElement("td");
  actionsTd.className = "row-actions";

  const toggleBtn = document.createElement("button");
  toggleBtn.textContent = task.completed ? "Als offen markieren" : "Abhaken";
  toggleBtn.className = "secondary";
  toggleBtn.onclick = async () => {
    await apiFetch(`/tasks/${task.id}/toggle`, { method: "PATCH" });
    await refreshTasks();
  };
  actionsTd.appendChild(toggleBtn);

  const plus10Btn = document.createElement("button");
  plus10Btn.textContent = "+10";
  plus10Btn.className = "secondary";
  plus10Btn.onclick = async () => {
    const statusEl = document.getElementById("task-list-error");
    statusEl.textContent = "";
    try {
      await apiFetch(`/tasks/${task.id}/plus10`, { method: "POST" });
      await refreshTasks();
    } catch (err) {
      statusEl.textContent = `Fehler bei "${task.title}": ${err.message}`;
    }
  };
  actionsTd.appendChild(plus10Btn);

  const assignSelect = document.createElement("select");
  const noneOption = document.createElement("option");
  noneOption.value = "";
  noneOption.textContent = "— niemand —";
  assignSelect.appendChild(noneOption);
  for (const user of users) {
    const option = document.createElement("option");
    option.value = String(user.id);
    option.textContent = user.name;
    if (task.assigneeUserId === user.id) option.selected = true;
    assignSelect.appendChild(option);
  }
  assignSelect.onchange = async () => {
    const userId = assignSelect.value ? Number(assignSelect.value) : null;
    await apiFetch(`/tasks/${task.id}/assignee`, {
      method: "PUT",
      body: JSON.stringify({ userId }),
    });
    await refreshTasks();
  };
  actionsTd.appendChild(assignSelect);

  const deleteBtn = document.createElement("button");
  deleteBtn.textContent = "Löschen";
  deleteBtn.className = "danger";
  deleteBtn.onclick = async () => {
    await apiFetch(`/tasks/${task.id}`, { method: "DELETE" });
    await refreshTasks();
  };
  actionsTd.appendChild(deleteBtn);

  tr.appendChild(actionsTd);
  return tr;
}

async function refreshTasks() {
  const query = buildTaskListQuery();
  const tasks = await apiFetch(`/tasks${query ? `?${query}` : ""}`);
  const tbody = document.getElementById("task-table-body");
  tbody.innerHTML = "";
  for (const task of tasks) {
    tbody.appendChild(renderTaskRow(task));
  }
}

async function loadAutoPlus10Setting() {
  const setting = await apiFetch("/settings/auto-plus10");
  document.getElementById("auto-plus10-toggle").checked = setting.enabled;
}

function setupNewTaskForm() {
  const form = document.getElementById("new-task-form");
  const errorEl = document.getElementById("new-task-error");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.textContent = "";
    const assigneeValue = document.getElementById("task-assignee").value;
    const body = {
      title: document.getElementById("task-title").value,
      description: document.getElementById("task-description").value || null,
      dueDate: document.getElementById("task-due-date").value || null,
      assigneeUserId: assigneeValue ? Number(assigneeValue) : null,
      priority: document.getElementById("task-priority").value,
    };
    try {
      await apiFetch("/tasks", { method: "POST", body: JSON.stringify(body) });
      form.reset();
      document.getElementById("task-priority").value = "medium";
      await refreshTasks();
    } catch (err) {
      errorEl.textContent = err.message;
    }
  });
}

function setupAiCreateForm() {
  const form = document.getElementById("ai-create-form");
  const errorEl = document.getElementById("ai-create-error");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.textContent = "";
    const text = document.getElementById("ai-create-text").value;
    try {
      await apiFetch("/tasks/ai-create", { method: "POST", body: JSON.stringify({ text }) });
      form.reset();
      await refreshTasks();
    } catch (err) {
      errorEl.textContent = err.message;
    }
  });
}

function setupAiAskForm() {
  const form = document.getElementById("ai-ask-form");
  const answerEl = document.getElementById("ai-answer");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const userId = Number(document.getElementById("ask-user").value);
    const question = document.getElementById("ask-question").value;
    try {
      const result = await apiFetch(`/users/${userId}/ask`, {
        method: "POST",
        body: JSON.stringify({ question }),
      });
      answerEl.textContent = result.answer;
    } catch (err) {
      answerEl.textContent = `Fehler: ${err.message}`;
    }
  });
}

function setupAutoPlus10Toggle() {
  document.getElementById("auto-plus10-toggle").addEventListener("change", async (event) => {
    await apiFetch("/settings/auto-plus10", {
      method: "PUT",
      body: JSON.stringify({ enabled: event.target.checked }),
    });
    await refreshTasks();
  });
}

function setupFilters() {
  document.getElementById("refresh-button").addEventListener("click", refreshTasks);
  for (const id of ["sort-by", "sort-order", "filter-assignee", "filter-completed"]) {
    document.getElementById(id).addEventListener("change", refreshTasks);
  }
}

function setupCsvImport() {
  document.getElementById("import-file").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const resultEl = document.getElementById("import-result");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await fetch(`${API_BASE}/tasks/import`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      resultEl.textContent = `${data.created.length} Task(s) importiert, ${data.errors.length} Zeile(n) abgelehnt.`;
      await refreshTasks();
    } catch (err) {
      resultEl.textContent = `Import fehlgeschlagen: ${err.message}`;
    } finally {
      event.target.value = "";
    }
  });
}

async function init() {
  await loadUsers();
  await loadAutoPlus10Setting();
  await refreshTasks();
  setupNewTaskForm();
  setupAiCreateForm();
  setupAiAskForm();
  setupAutoPlus10Toggle();
  setupFilters();
  setupCsvImport();
}

init();
