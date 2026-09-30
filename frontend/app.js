const API_BASE = "/api";
const MONTH_NAMES = [
  "Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez",
];

let users = [];
let statusFilter = "open"; // "open" | "done" | "all"

// Pro User eine eigene, gedämpfte Avatarfarbe - bewusst getrennt von der
// Akzentfarbe (Dringlichkeit) und der KI-Farbe (Sternchen-Aktionen).
const AVATAR_COLORS = {
  1: { bg: "#e3ece4", ink: "#3f6b4c" }, // Alice - Salbeigrün
  2: { bg: "#e1e8f0", ink: "#375170" }, // Bob - Taubenblau
  3: { bg: "#f0e3ea", ink: "#7a3b57" }, // Carol - Pflaume
};

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

function userById(userId) {
  return users.find((u) => u.id === userId) || null;
}

function initialOf(name) {
  return name.charAt(0).toUpperCase();
}

function priorityLabel(priority) {
  return { low: "Niedrig", medium: "Mittel", high: "Hoch" }[priority] || priority;
}

function parseIsoDate(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatDueDate(isoDate) {
  const date = parseIsoDate(isoDate);
  const today = new Date();
  const parts = `${date.getDate()} ${MONTH_NAMES[date.getMonth()]}`;
  return date.getFullYear() === today.getFullYear() ? parts : `${parts} ${date.getFullYear()}`;
}

function isOverdue(isoDate) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return parseIsoDate(isoDate) < today;
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

  if (sortBy) params.set("sortBy", sortBy);
  if (order) params.set("order", order);
  if (assignee) params.set("assigneeUserId", assignee);
  if (statusFilter === "open") params.set("completed", "false");
  if (statusFilter === "done") params.set("completed", "true");
  return params.toString();
}

function createAssigneePill(task) {
  const label = document.createElement("label");
  label.className = "pill pill-assignee";
  const currentUser = userById(task.assigneeUserId);
  if (!currentUser) label.classList.add("is-unassigned");

  const avatar = document.createElement("span");
  avatar.className = "avatar";
  avatar.textContent = currentUser ? initialOf(currentUser.name) : "?";
  const colors = currentUser ? AVATAR_COLORS[currentUser.id] : null;
  if (colors) {
    avatar.style.background = colors.bg;
    avatar.style.color = colors.ink;
  }
  label.appendChild(avatar);

  const select = document.createElement("select");
  const noneOption = document.createElement("option");
  noneOption.value = "";
  noneOption.textContent = "Niemand";
  select.appendChild(noneOption);
  for (const user of users) {
    const option = document.createElement("option");
    option.value = String(user.id);
    option.textContent = user.name;
    if (task.assigneeUserId === user.id) option.selected = true;
    select.appendChild(option);
  }
  select.onclick = (event) => event.stopPropagation();
  select.onchange = async () => {
    const userId = select.value ? Number(select.value) : null;
    await apiFetch(`/tasks/${task.id}/assignee`, {
      method: "PUT",
      body: JSON.stringify({ userId }),
    });
    await refreshTasks();
  };
  label.appendChild(select);
  return label;
}

function renderTaskRow(task) {
  const li = document.createElement("li");
  li.className = "task-row";
  li.dataset.id = String(task.id);

  const checkBtn = document.createElement("button");
  checkBtn.type = "button";
  checkBtn.className = "check-circle";
  checkBtn.setAttribute("aria-label", task.completed ? "Als offen markieren" : "Task abhaken");
  if (task.completed) checkBtn.classList.add("is-checked");
  checkBtn.innerHTML = '<span class="icon icon-check"></span>';
  checkBtn.onclick = () => handleToggle(task, li);
  li.appendChild(checkBtn);

  const plus10Btn = document.createElement("button");
  plus10Btn.type = "button";
  plus10Btn.className = "plus10-btn";
  plus10Btn.textContent = "+10";
  if (task.dueDate) {
    plus10Btn.title = "Fälligkeitsdatum um 10 Werktage verschieben";
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
  } else {
    plus10Btn.disabled = true;
    plus10Btn.title = "Kein Fälligkeitsdatum gesetzt";
  }
  li.appendChild(plus10Btn);

  const main = document.createElement("div");
  main.className = "task-main";

  const title = document.createElement("p");
  title.className = "task-title";
  title.textContent = task.title;
  main.appendChild(title);

  const meta = document.createElement("div");
  meta.className = "task-meta";

  if (task.dueDate) {
    const datePill = document.createElement("span");
    datePill.className = "pill pill-date";
    if (!task.completed && isOverdue(task.dueDate)) datePill.classList.add("is-overdue");
    datePill.innerHTML = `<span class="icon icon-calendar"></span>${formatDueDate(task.dueDate)}`;
    meta.appendChild(datePill);
  }

  const priorityPill = document.createElement("span");
  priorityPill.className = `pill pill-priority priority-${task.priority}`;
  priorityPill.innerHTML = `<span class="icon icon-flag"></span>${priorityLabel(task.priority)}`;
  meta.appendChild(priorityPill);

  meta.appendChild(createAssigneePill(task));

  main.appendChild(meta);
  li.appendChild(main);

  return li;
}

async function handleToggle(task, rowEl) {
  rowEl.classList.add("is-completing");
  const checkBtn = rowEl.querySelector(".check-circle");
  checkBtn.classList.toggle("is-checked", !task.completed);
  await new Promise((resolve) => setTimeout(resolve, 260));
  await apiFetch(`/tasks/${task.id}/toggle`, { method: "PATCH" });
  await refreshTasks();
}

async function refreshTasks() {
  const query = buildTaskListQuery();
  const tasks = await apiFetch(`/tasks${query ? `?${query}` : ""}`);
  const list = document.getElementById("task-list");
  const emptyState = document.getElementById("empty-state");
  list.innerHTML = "";
  for (const task of tasks) {
    list.appendChild(renderTaskRow(task));
  }
  emptyState.hidden = tasks.length > 0;

  const heading = { open: "Offene Tasks", done: "Erledigte Tasks", all: "Alle Tasks" }[statusFilter];
  document.getElementById("list-heading").textContent = heading;
  document.getElementById("list-count").textContent =
    tasks.length === 1 ? "1 Task" : `${tasks.length} Tasks`;
}

async function loadAutoPlus10Setting() {
  const setting = await apiFetch("/settings/auto-plus10");
  document.getElementById("auto-plus10-toggle").checked = setting.enabled;
}

function setupStatusFilter() {
  const buttons = document.querySelectorAll("#status-filter .segmented-option");
  for (const button of buttons) {
    button.addEventListener("click", async () => {
      statusFilter = button.dataset.value;
      for (const other of buttons) other.classList.toggle("is-active", other === button);
      await refreshTasks();
    });
  }
}

function setupSidebarControls() {
  for (const id of ["sort-by", "sort-order", "filter-assignee"]) {
    document.getElementById(id).addEventListener("change", refreshTasks);
  }

  document.getElementById("auto-plus10-toggle").addEventListener("change", async (event) => {
    await apiFetch("/settings/auto-plus10", {
      method: "PUT",
      body: JSON.stringify({ enabled: event.target.checked }),
    });
    await refreshTasks();
  });

  document.getElementById("ask-button").addEventListener("click", async () => {
    const userId = Number(document.getElementById("ask-user").value);
    const question = document.getElementById("ask-question").value;
    const answerEl = document.getElementById("ai-answer");
    if (!question.trim()) return;
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

  document.getElementById("import-file").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const resultEl = document.getElementById("import-result");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await fetch(`${API_BASE}/tasks/import`, { method: "POST", body: formData });
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

function setupAddPanels() {
  const newTaskForm = document.getElementById("new-task-form");
  const aiCreateForm = document.getElementById("ai-create-form");
  const showAddTaskBtn = document.getElementById("show-add-task");
  const showAiTaskBtn = document.getElementById("show-ai-task");

  function openPanel(panel) {
    newTaskForm.hidden = panel !== newTaskForm;
    aiCreateForm.hidden = panel !== aiCreateForm;
    const firstInput = panel.querySelector("input");
    if (firstInput) firstInput.focus();
  }

  function closePanels() {
    newTaskForm.hidden = true;
    aiCreateForm.hidden = true;
  }

  showAddTaskBtn.addEventListener("click", () => openPanel(newTaskForm));
  showAiTaskBtn.addEventListener("click", () => openPanel(aiCreateForm));
  document.getElementById("cancel-new-task").addEventListener("click", closePanels);
  document.getElementById("cancel-ai-task").addEventListener("click", closePanels);

  const newTaskError = document.getElementById("new-task-error");
  newTaskForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    newTaskError.textContent = "";
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
      newTaskForm.reset();
      document.getElementById("task-priority").value = "medium";
      closePanels();
      await refreshTasks();
    } catch (err) {
      newTaskError.textContent = err.message;
    }
  });

  const aiCreateError = document.getElementById("ai-create-error");
  aiCreateForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    aiCreateError.textContent = "";
    const text = document.getElementById("ai-create-text").value;
    try {
      await apiFetch("/tasks/ai-create", { method: "POST", body: JSON.stringify({ text }) });
      aiCreateForm.reset();
      closePanels();
      await refreshTasks();
    } catch (err) {
      aiCreateError.textContent = err.message;
    }
  });
}

async function init() {
  await loadUsers();
  await loadAutoPlus10Setting();
  await refreshTasks();
  setupStatusFilter();
  setupSidebarControls();
  setupAddPanels();
}

init();
