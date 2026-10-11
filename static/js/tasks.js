/**
 * Global Cross-Project Tasks List Controller
 */

let currentPage = 1;
let totalTasks = 0;
let nextPageUrl = null;
let prevPageUrl = null;

async function initGlobalTasks() {
  await populateProjectFilter();
  await loadGlobalTasks();
  initTaskListeners();
}

async function populateProjectFilter() {
  const select = document.getElementById('taskProjectFilter');
  if (!select) return;

  try {
    const projects = await apiRequest('/api/projects/');
    const optionsHtml = projects.map(p => `
      <option value="${p.id}">${escapeHtml(p.name)}</option>
    `).join('');
    select.innerHTML = '<option value="">All Projects</option>' + optionsHtml;
  } catch (err) {}
}

async function loadGlobalTasks(page = 1) {
  currentPage = page;
  const tbody = document.getElementById('tasksTableTbody');
  const search = document.getElementById('taskSearchInput')?.value.trim();
  const projectId = document.getElementById('taskProjectFilter')?.value;
  const status = document.getElementById('taskStatusFilter')?.value;
  const priority = document.getElementById('taskPriorityFilter')?.value;
  const ordering = document.getElementById('taskSortFilter')?.value || '-created_at';

  let url = `/api/tasks/?page=${currentPage}&ordering=${ordering}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  if (projectId) url += `&project_id=${projectId}`;
  if (status) url += `&status=${status}`;
  if (priority) url += `&priority=${priority}`;

  try {
    const res = await apiRequest(url);
    const tasks = res.results || [];
    totalTasks = res.count || 0;
    nextPageUrl = res.next;
    prevPageUrl = res.previous;

    updatePaginationControls();

    if (tasks.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="text-center text-muted py-5 small">
            <i class="bi bi-inbox fs-2 d-block mb-2 text-secondary opacity-50"></i>
            No tasks found matching current filters.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = tasks.map(t => {
      const prioLower = (t.priority || 'medium').toLowerCase();
      const statusLabels = { TODO: 'To Do', IN_PROGRESS: 'In Progress', DONE: 'Done' };
      const statusClass = { TODO: 'todo', IN_PROGRESS: 'in_progress', DONE: 'done' };
      const assignee = t.assignee;
      const initials = assignee ? (assignee.username || 'U')[0].toUpperCase() : null;
      const avatarBg = assignee ? (assignee.avatar_color || '#3b82f6') : '#64748b';

      return `
        <tr>
          <td class="ps-3 py-3">
            <a href="/projects/${t.project}/" class="text-decoration-none fw-semibold text-light hover-accent">
              ${escapeHtml(t.title)}
            </a>
            ${t.is_overdue ? '<span class="badge-overdue ms-2"><i class="bi bi-clock me-1"></i>Overdue</span>' : ''}
          </td>
          <td class="py-3">
            <a href="/projects/${t.project}/" class="text-muted small text-decoration-none">
              <i class="bi bi-folder2 me-1"></i>${escapeHtml(t.project_name)}
            </a>
          </td>
          <td class="py-3">
            <span class="d-inline-flex align-items-center gap-1 small">
              <span class="column-dot ${statusClass[t.status]}"></span>
              <span>${statusLabels[t.status] || t.status}</span>
            </span>
          </td>
          <td class="py-3">
            <span class="badge-prio ${prioLower}">${escapeHtml(t.priority)}</span>
          </td>
          <td class="py-3">
            ${assignee ? `
              <div class="d-flex align-items-center gap-2">
                <div class="avatar-initials" style="width: 22px; height: 22px; font-size: 0.68rem; background-color: ${avatarBg};">
                  ${initials}
                </div>
                <span class="small text-muted">${escapeHtml(assignee.display_name || assignee.username)}</span>
              </div>
            ` : '<span class="text-muted small">Unassigned</span>'}
          </td>
          <td class="py-3 text-muted small">
            ${t.due_date ? escapeHtml(t.due_date) : '—'}
          </td>
          <td class="pe-3 py-3 text-end">
            <a href="/projects/${t.project}/" class="btn btn-sm btn-devtask-secondary py-1 px-2" style="font-size: 0.78rem;">
              View on Board →
            </a>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="text-center text-danger py-4 small">
          Failed to load tasks.
        </td>
      </tr>
    `;
  }
}

function updatePaginationControls() {
  const info = document.getElementById('paginationInfo');
  const prevBtn = document.getElementById('prevPageBtn');
  const nextBtn = document.getElementById('nextPageBtn');

  if (info) info.textContent = `Total tasks: ${totalTasks} (Page ${currentPage})`;
  if (prevBtn) prevBtn.disabled = !prevPageUrl;
  if (nextBtn) nextBtn.disabled = !nextPageUrl;
}

function initTaskListeners() {
  document.getElementById('taskSearchInput')?.addEventListener('input', debounce(() => loadGlobalTasks(1), 300));
  document.getElementById('taskProjectFilter')?.addEventListener('change', () => loadGlobalTasks(1));
  document.getElementById('taskStatusFilter')?.addEventListener('change', () => loadGlobalTasks(1));
  document.getElementById('taskPriorityFilter')?.addEventListener('change', () => loadGlobalTasks(1));
  document.getElementById('taskSortFilter')?.addEventListener('change', () => loadGlobalTasks(1));

  document.getElementById('prevPageBtn')?.addEventListener('click', () => {
    if (prevPageUrl && currentPage > 1) loadGlobalTasks(currentPage - 1);
  });

  document.getElementById('nextPageBtn')?.addEventListener('click', () => {
    if (nextPageUrl) loadGlobalTasks(currentPage + 1);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('tasksTableTbody')) {
    initGlobalTasks();
  }
});
