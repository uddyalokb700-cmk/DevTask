/**
 * DevTask Kanban Board, Drag & Drop Engine, and Task Details Controller
 */

let currentProjectId = null;
let currentProject = null;
let projectMembers = [];
let boardTasks = [];
let activeTaskInDrawer = null;
let draggedTaskId = null;
let dragSourceStatus = null;
let socket = null;

// Initialize board on load
document.addEventListener('DOMContentLoaded', () => {
  const projInput = document.getElementById('currentProjectId');
  if (!projInput) return;
  currentProjectId = projInput.value;

  initBoard();
  initDragAndDrop();
  initEventListeners();
  initWebSocket();
});

async function initBoard() {
  setSyncStatus('loading', 'Loading board data...');
  try {
    // 1. Fetch Project Details & Members
    currentProject = await apiRequest(`/api/projects/${currentProjectId}/`);
    projectMembers = currentProject.members || [];

    // Update Header Counts & UI
    const teamCountBadge = document.getElementById('teamCountBadge');
    if (teamCountBadge) teamCountBadge.textContent = projectMembers.length;

    // Populate Assignee Selects
    populateAssigneeSelects();

    // 2. Fetch Tasks
    await loadTasks();

    setSyncStatus('synced', 'Board synced with server');
  } catch (err) {
    setSyncStatus('error', 'Error syncing board');
    console.error('Board initialization failed:', err);
  }
}

async function loadTasks() {
  const search = document.getElementById('boardSearchInput')?.value.trim();
  const priority = document.getElementById('boardPriorityFilter')?.value;
  const assignee = document.getElementById('boardAssigneeFilter')?.value;
  const ordering = document.getElementById('boardSortFilter')?.value || 'position';

  let url = `/api/tasks/?project_id=${currentProjectId}&page_size=100&ordering=${ordering}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  if (priority) url += `&priority=${priority}`;
  if (assignee) url += `&assignee_id=${assignee}`;

  try {
    const res = await apiRequest(url);
    boardTasks = res.results || [];
    renderBoard();
  } catch (err) {
    console.error('Failed to load tasks:', err);
  }
}

function renderBoard() {
  const columns = {
    TODO: document.getElementById('col-TODO'),
    IN_PROGRESS: document.getElementById('col-IN_PROGRESS'),
    DONE: document.getElementById('col-DONE')
  };

  const counts = { TODO: 0, IN_PROGRESS: 0, DONE: 0 };

  // Clear drop zones
  Object.values(columns).forEach(col => { if (col) col.innerHTML = ''; });

  // Group tasks
  boardTasks.forEach(task => {
    const col = columns[task.status];
    if (col) {
      counts[task.status]++;
      col.appendChild(createTaskCardElement(task));
    }
  });

  // Update counters
  document.getElementById('count-TODO').textContent = counts.TODO;
  document.getElementById('count-IN_PROGRESS').textContent = counts.IN_PROGRESS;
  document.getElementById('count-DONE').textContent = counts.DONE;

  // Empty states
  Object.entries(columns).forEach(([status, col]) => {
    if (col && counts[status] === 0) {
      col.innerHTML = `
        <div class="text-center text-muted py-4 small opacity-75">
          <i class="bi bi-inbox d-block mb-1 fs-5"></i>
          No tasks in ${status.replace('_', ' ').toLowerCase()}
        </div>
      `;
    }
  });
}

function createTaskCardElement(task) {
  const card = document.createElement('div');
  card.className = 'task-card';
  card.id = `task-card-${task.id}`;
  card.setAttribute('draggable', 'true');
  card.setAttribute('data-task-id', task.id);
  card.setAttribute('data-status', task.status);

  const prioLower = (task.priority || 'medium').toLowerCase();
  const assignee = task.assignee;
  const initials = assignee ? (assignee.username || 'U')[0].toUpperCase() : null;
  const avatarBg = assignee ? (assignee.avatar_color || '#3b82f6') : '#64748b';

  card.innerHTML = `
    <div class="d-flex justify-content-between align-items-start gap-2 mb-2">
      <span class="badge-prio ${prioLower}">${escapeHtml(task.priority)}</span>
      ${task.is_overdue ? '<span class="badge-overdue"><i class="bi bi-clock me-1"></i>Overdue</span>' : ''}

      <!-- Accessible fallback move dropdown -->
      <div class="dropdown ms-auto" onclick="event.stopPropagation();">
        <button class="btn btn-sm btn-link text-muted p-0" data-bs-toggle="dropdown" aria-expanded="false" title="Move card">
          <i class="bi bi-three-dots"></i>
        </button>
        <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end shadow small">
          <li class="dropdown-header small text-muted">Move to column:</li>
          <li><button class="dropdown-item small" onclick="moveTaskAccessible('${task.id}', 'TODO')"><span class="column-dot todo d-inline-block me-1"></span> To Do</button></li>
          <li><button class="dropdown-item small" onclick="moveTaskAccessible('${task.id}', 'IN_PROGRESS')"><span class="column-dot in_progress d-inline-block me-1"></span> In Progress</button></li>
          <li><button class="dropdown-item small" onclick="moveTaskAccessible('${task.id}', 'DONE')"><span class="column-dot done d-inline-block me-1"></span> Done</button></li>
        </ul>
      </div>
    </div>

    <div class="task-card-title">${escapeHtml(task.title)}</div>

    <div class="task-card-meta">
      <div class="d-flex align-items-center gap-2">
        ${assignee ? `
          <div class="avatar-initials" style="width: 22px; height: 22px; font-size: 0.68rem; background-color: ${avatarBg};" title="${escapeHtml(assignee.display_name || assignee.username)}">
            ${initials}
          </div>
          <span class="small text-muted text-truncate" style="max-width: 90px; font-size: 0.75rem;">${escapeHtml(assignee.display_name || assignee.username)}</span>
        ` : `
          <span class="text-muted small" style="font-size: 0.75rem;"><i class="bi bi-person-dash me-1"></i>Unassigned</span>
        `}
      </div>

      <div class="d-flex align-items-center gap-2 text-muted small" style="font-size: 0.75rem;">
        ${task.due_date ? `<span><i class="bi bi-calendar3 me-1"></i>${escapeHtml(task.due_date)}</span>` : ''}
        ${(task.comments_count || 0) > 0 ? `<span><i class="bi bi-chat-dots me-1"></i>${task.comments_count}</span>` : ''}
      </div>
    </div>
  `;

  card.addEventListener('click', () => openTaskDetailDrawer(task.id));
  return card;
}

// Drag & Drop engine
function initDragAndDrop() {
  document.addEventListener('dragstart', (e) => {
    const card = e.target.closest('.task-card');
    if (!card) return;
    draggedTaskId = card.getAttribute('data-task-id');
    dragSourceStatus = card.getAttribute('data-status');
    card.classList.add('is-dragging');
    e.dataTransfer.setData('text/plain', draggedTaskId);
    e.dataTransfer.effectAllowed = 'move';
  });

  document.addEventListener('dragend', (e) => {
    const card = e.target.closest('.task-card');
    if (card) card.classList.remove('is-dragging');
    document.querySelectorAll('.kanban-drop-zone').forEach(z => z.classList.remove('drag-over'));
  });

  document.querySelectorAll('.kanban-drop-zone').forEach(dropZone => {
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', (e) => {
      if (!dropZone.contains(e.relatedTarget)) {
        dropZone.classList.remove('drag-over');
      }
    });

    dropZone.addEventListener('drop', async (e) => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');

      const taskId = e.dataTransfer.getData('text/plain') || draggedTaskId;
      const targetStatus = dropZone.getAttribute('data-status');

      if (!taskId || !targetStatus) return;

      const task = boardTasks.find(t => t.id === taskId);
      if (!task) return;

      const previousStatus = task.status;
      if (previousStatus === targetStatus) return; // Same column drop

      // Optimistic UI update
      task.status = targetStatus;
      renderBoard();
      setSyncStatus('loading', 'Moving task...');

      try {
        await apiRequest(`/api/tasks/${taskId}/reorder/`, {
          method: 'POST',
          body: {
            status: targetStatus,
            position: computeNewPosition(targetStatus)
          }
        });
        setSyncStatus('synced', 'Board synced with server');
      } catch (err) {
        // Rollback on failure
        task.status = previousStatus;
        renderBoard();
        setSyncStatus('error', 'Failed to move task. Reverted.');
        showToast('Failed to update task column. Changes reverted.', 'error');
      }
    });
  });
}

async function moveTaskAccessible(taskId, targetStatus) {
  const task = boardTasks.find(t => t.id === taskId);
  if (!task || task.status === targetStatus) return;

  const prevStatus = task.status;
  task.status = targetStatus;
  renderBoard();
  setSyncStatus('loading', 'Updating task...');

  try {
    await apiRequest(`/api/tasks/${taskId}/reorder/`, {
      method: 'POST',
      body: {
        status: targetStatus,
        position: computeNewPosition(targetStatus)
      }
    });
    setSyncStatus('synced', 'Board synced with server');
    showToast(`Task moved to ${targetStatus.replace('_', ' ')}.`, 'info');
  } catch (err) {
    task.status = prevStatus;
    renderBoard();
    setSyncStatus('error', 'Failed to move task.');
  }
}

function computeNewPosition(targetStatus) {
  const tasksInCol = boardTasks.filter(t => t.status === targetStatus);
  if (tasksInCol.length === 0) return 1.0;
  const maxPos = Math.max(...tasksInCol.map(t => t.position || 0));
  return maxPos + 1.0;
}

// Task Detail Drawer
async function openTaskDetailDrawer(taskId) {
  try {
    const task = await apiRequest(`/api/tasks/${taskId}/`);
    activeTaskInDrawer = task;

    document.getElementById('drawerTaskIdLabel').textContent = `TASK-${task.id.slice(0, 8)}`;
    document.getElementById('drawerTaskTitleInput').value = task.title;
    document.getElementById('drawerTaskStatusSelect').value = task.status;
    document.getElementById('drawerTaskPrioritySelect').value = task.priority;
    document.getElementById('drawerTaskAssigneeSelect').value = task.assignee?.id || '';
    document.getElementById('drawerTaskDueDateInput').value = task.due_date || '';
    document.getElementById('drawerTaskDescTextarea').value = task.description || '';

    const prioBadge = document.getElementById('drawerTaskPrioBadge');
    prioBadge.className = `badge-prio ${(task.priority || 'medium').toLowerCase()}`;
    prioBadge.textContent = task.priority;

    // Load comments
    await loadTaskComments(taskId);

    const drawer = new bootstrap.Offcanvas(document.getElementById('taskDetailDrawer'));
    drawer.show();
  } catch (err) {
    console.error('Failed to open task details:', err);
  }
}

async function loadTaskComments(taskId) {
  const stream = document.getElementById('drawerCommentsStream');
  const countBadge = document.getElementById('drawerCommentCount');

  try {
    const comments = await apiRequest(`/api/tasks/${taskId}/comments/`);
    countBadge.textContent = comments.length;

    if (comments.length === 0) {
      stream.innerHTML = '<div class="text-center text-muted small py-3">No comments yet. Start the conversation!</div>';
      return;
    }

    stream.innerHTML = comments.map(c => `
      <div class="comment-card">
        <div class="d-flex align-items-center justify-content-between mb-2">
          <div class="d-flex align-items-center gap-2">
            <div class="avatar-initials" style="width: 22px; height: 22px; font-size: 0.68rem; background-color: ${c.author?.avatar_color || '#3b82f6'};">
              ${(c.author?.username || 'U')[0].toUpperCase()}
            </div>
            <span class="fw-semibold small text-light">${escapeHtml(c.author?.display_name || c.author?.username)}</span>
          </div>
          <span class="text-muted" style="font-size: 0.72rem;">${formatRelativeTime(c.created_at)}</span>
        </div>
        <div class="small text-secondary" style="white-space: pre-wrap;">${escapeHtml(c.body)}</div>
      </div>
    `).join('');
  } catch (err) {
    stream.innerHTML = '<div class="text-center text-danger small py-2">Failed to load comments.</div>';
  }
}

// Team Management
function populateAssigneeSelects() {
  const modalSelect = document.getElementById('taskAssigneeSelect');
  const drawerSelect = document.getElementById('drawerTaskAssigneeSelect');
  const filterSelect = document.getElementById('boardAssigneeFilter');

  const optionsHtml = projectMembers.map(m => `
    <option value="${m.user.id}">${escapeHtml(m.user.display_name || m.user.username)} (${m.role})</option>
  `).join('');

  if (modalSelect) modalSelect.innerHTML = '<option value="">Unassigned</option>' + optionsHtml;
  if (drawerSelect) drawerSelect.innerHTML = '<option value="">Unassigned</option>' + optionsHtml;
  if (filterSelect) {
    filterSelect.innerHTML = `
      <option value="">All Assignees</option>
      <option value="unassigned">Unassigned</option>
      ${projectMembers.map(m => `<option value="${m.user.id}">${escapeHtml(m.user.display_name || m.user.username)}</option>`).join('')}
    `;
  }
}

async function renderTeamList() {
  const container = document.getElementById('membersListContainer');
  if (!container) return;

  try {
    const members = await apiRequest(`/api/projects/${currentProjectId}/members/`);
    projectMembers = members;
    populateAssigneeSelects();

    container.innerHTML = members.map(m => `
      <div class="p-2 rounded-3 d-flex align-items-center justify-content-between" style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle);">
        <div class="d-flex align-items-center gap-2">
          <div class="avatar-initials" style="width: 28px; height: 28px; font-size: 0.75rem; background-color: ${m.user.avatar_color || '#3b82f6'};">
            ${(m.user.username || 'U')[0].toUpperCase()}
          </div>
          <div>
            <div class="fw-semibold small text-light">${escapeHtml(m.user.display_name || m.user.username)}</div>
            <div class="text-muted" style="font-size: 0.72rem;">@${escapeHtml(m.user.username)}</div>
          </div>
        </div>

        <div class="d-flex align-items-center gap-2">
          <span class="badge ${m.role === 'OWNER' ? 'bg-primary-subtle text-primary' : 'bg-secondary-subtle text-secondary'} small" style="font-size: 0.72rem;">
            ${escapeHtml(m.role)}
          </span>
          ${m.role !== 'OWNER' ? `
            <button class="btn btn-sm btn-link text-danger p-0" title="Remove member" onclick="removeMember(${m.id})">
              <i class="bi bi-x-circle"></i>
            </button>
          ` : ''}
        </div>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = '<div class="text-center text-danger small py-2">Failed to load team members.</div>';
  }
}

async function removeMember(membershipId) {
  if (!confirm('Remove this member from the project? Their assigned tasks will be unassigned.')) return;
  try {
    await apiRequest(`/api/projects/${currentProjectId}/members/${membershipId}/`, {
      method: 'DELETE'
    });
    showToast('Member removed from project.', 'info');
    renderTeamList();
    loadTasks();
  } catch (err) {}
}

async function renderActivityStream() {
  const container = document.getElementById('activityStreamContainer');
  if (!container) return;

  try {
    const res = await apiRequest(`/api/projects/${currentProjectId}/activity/`);
    const logs = res.results || [];

    if (logs.length === 0) {
      container.innerHTML = '<div class="text-center text-muted small py-4">No activity logged yet.</div>';
      return;
    }

    container.innerHTML = logs.map(a => {
      const actorName = a.actor?.display_name || a.actor?.username || 'System';
      return `
        <div class="activity-item">
          <div class="avatar-initials mt-1" style="width: 24px; height: 24px; font-size: 0.68rem; background-color: ${a.actor?.avatar_color || '#3b82f6'};">
            ${(actorName)[0].toUpperCase()}
          </div>
          <div class="flex-grow-1">
            <div class="text-light">
              <span class="fw-semibold">${escapeHtml(actorName)}</span>
              <span class="text-secondary ms-1">${escapeHtml(a.action.replace(/_/g, ' ').toLowerCase())}</span>
            </div>
            ${a.task_title ? `<div class="text-muted small">Task: "${escapeHtml(a.task_title)}"</div>` : ''}
            <div class="text-muted" style="font-size: 0.72rem;">${formatRelativeTime(a.created_at)}</div>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = '<div class="text-center text-danger small py-3">Failed to load activity stream.</div>';
  }
}

function openCreateTaskModalWithStatus(status) {
  document.getElementById('taskStatusSelect').value = status;
  const modal = new bootstrap.Modal(document.getElementById('createTaskModal'));
  modal.show();
}

function setSyncStatus(state, message) {
  const spinner = document.getElementById('syncSpinner');
  const text = document.getElementById('syncStatusText');
  if (!text) return;

  if (state === 'loading') {
    if (spinner) spinner.classList.remove('d-none');
    text.innerHTML = `<span class="text-primary me-1"><i class="bi bi-arrow-repeat spin-animation"></i></span>${escapeHtml(message)}`;
  } else if (state === 'synced') {
    if (spinner) spinner.classList.add('d-none');
    text.innerHTML = `<span class="text-success me-1"><i class="bi bi-check2"></i></span>${escapeHtml(message)}`;
  } else if (state === 'error') {
    if (spinner) spinner.classList.add('d-none');
    text.innerHTML = `<span class="text-danger me-1"><i class="bi bi-exclamation-circle"></i></span>${escapeHtml(message)}`;
  }
}

// WebSocket connection for real-time task sync
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/projects/${currentProjectId}/`;

  try {
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('DevTask WebSocket connected for project:', currentProjectId);
    };

    socket.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        console.log('Real-time event received:', payload);
        // Refresh board on relevant updates
        loadTasks();
      } catch (err) {}
    };

    socket.onclose = (e) => {
      // Avoid reconnect storms if rejected due to authentication (4001) or unauthorized project access (4003)
      if (e.code === 4001 || e.code === 4003) {
        console.warn(`[DevTask WS] Connection closed with code ${e.code} (${e.code === 4001 ? 'Unauthenticated' : 'Unauthorized'}). Auto-reconnect aborted.`);
        return;
      }
      // Reconnect after delay on transient disconnections
      setTimeout(() => {
        if (document.getElementById('currentProjectId')) initWebSocket();
      }, 5000);
    };
  } catch (err) {
    console.debug('WebSocket connection skipped or unsupported:', err);
  }
}

// Event Listeners setup
function initEventListeners() {
  // Filters
  document.getElementById('boardSearchInput')?.addEventListener('input', debounce(() => loadTasks(), 300));
  document.getElementById('boardPriorityFilter')?.addEventListener('change', () => loadTasks());
  document.getElementById('boardAssigneeFilter')?.addEventListener('change', () => loadTasks());
  document.getElementById('boardSortFilter')?.addEventListener('change', () => loadTasks());

  // Create Task Form
  const createTaskForm = document.getElementById('createTaskForm');
  if (createTaskForm) {
    createTaskForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const title = document.getElementById('taskTitleInput').value.trim();
      const description = document.getElementById('taskDescInput').value.trim();
      const status = document.getElementById('taskStatusSelect').value;
      const priority = document.getElementById('taskPrioritySelect').value;
      const assigneeId = document.getElementById('taskAssigneeSelect').value;
      const dueDate = document.getElementById('taskDueDateInput').value;

      try {
        await apiRequest('/api/tasks/', {
          method: 'POST',
          body: {
            project_id: currentProjectId,
            title,
            description,
            status,
            priority,
            assignee_id: assigneeId || null,
            due_date: dueDate || null
          }
        });
        showToast('Task created.', 'success');
        bootstrap.Modal.getInstance(document.getElementById('createTaskModal'))?.hide();
        createTaskForm.reset();
        loadTasks();
      } catch (err) {}
    });
  }

  // Drawer task auto-save handlers
  document.getElementById('drawerTaskTitleInput')?.addEventListener('change', async (e) => {
    if (!activeTaskInDrawer) return;
    const newTitle = e.target.value.trim();
    if (!newTitle) return;
    try {
      await apiRequest(`/api/tasks/${activeTaskInDrawer.id}/`, {
        method: 'PATCH',
        body: { title: newTitle }
      });
      loadTasks();
    } catch (err) {}
  });

  document.getElementById('drawerTaskStatusSelect')?.addEventListener('change', async (e) => {
    if (!activeTaskInDrawer) return;
    try {
      await apiRequest(`/api/tasks/${activeTaskInDrawer.id}/`, {
        method: 'PATCH',
        body: { status: e.target.value }
      });
      loadTasks();
    } catch (err) {}
  });

  document.getElementById('drawerTaskPrioritySelect')?.addEventListener('change', async (e) => {
    if (!activeTaskInDrawer) return;
    try {
      const prio = e.target.value;
      await apiRequest(`/api/tasks/${activeTaskInDrawer.id}/`, {
        method: 'PATCH',
        body: { priority: prio }
      });
      const badge = document.getElementById('drawerTaskPrioBadge');
      badge.className = `badge-prio ${prio.toLowerCase()}`;
      badge.textContent = prio;
      loadTasks();
    } catch (err) {}
  });

  document.getElementById('drawerTaskAssigneeSelect')?.addEventListener('change', async (e) => {
    if (!activeTaskInDrawer) return;
    try {
      await apiRequest(`/api/tasks/${activeTaskInDrawer.id}/`, {
        method: 'PATCH',
        body: { assignee_id: e.target.value || null }
      });
      loadTasks();
    } catch (err) {}
  });

  document.getElementById('drawerTaskDueDateInput')?.addEventListener('change', async (e) => {
    if (!activeTaskInDrawer) return;
    try {
      await apiRequest(`/api/tasks/${activeTaskInDrawer.id}/`, {
        method: 'PATCH',
        body: { due_date: e.target.value || null }
      });
      loadTasks();
    } catch (err) {}
  });

  document.getElementById('drawerSaveDescBtn')?.addEventListener('click', async () => {
    if (!activeTaskInDrawer) return;
    const desc = document.getElementById('drawerTaskDescTextarea').value;
    try {
      await apiRequest(`/api/tasks/${activeTaskInDrawer.id}/`, {
        method: 'PATCH',
        body: { description: desc }
      });
      showToast('Description updated.', 'success');
      loadTasks();
    } catch (err) {}
  });

  document.getElementById('drawerDeleteTaskBtn')?.addEventListener('click', async () => {
    if (!activeTaskInDrawer) return;
    if (!confirm('Permanently delete this task?')) return;
    try {
      await apiRequest(`/api/tasks/${activeTaskInDrawer.id}/`, {
        method: 'DELETE'
      });
      showToast('Task deleted.', 'info');
      bootstrap.Offcanvas.getInstance(document.getElementById('taskDetailDrawer'))?.hide();
      loadTasks();
    } catch (err) {}
  });

  // Drawer Comment submission
  document.getElementById('drawerPostCommentForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!activeTaskInDrawer) return;
    const input = document.getElementById('drawerCommentInput');
    const body = input.value.trim();
    if (!body) return;

    try {
      await apiRequest(`/api/tasks/${activeTaskInDrawer.id}/comments/`, {
        method: 'POST',
        body: { body }
      });
      input.value = '';
      loadTaskComments(activeTaskInDrawer.id);
      loadTasks();
    } catch (err) {}
  });

  // Team Drawer Trigger
  document.getElementById('openTeamDrawerBtn')?.addEventListener('click', () => {
    renderTeamList();
    const drawer = new bootstrap.Offcanvas(document.getElementById('teamDrawer'));
    drawer.show();
  });

  // Add Member Form
  document.getElementById('addMemberForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = document.getElementById('addMemberInput');
    const roleSelect = document.getElementById('addMemberRoleSelect');
    const username_or_email = input.value.trim();
    const role = roleSelect.value;

    try {
      await apiRequest(`/api/projects/${currentProjectId}/members/`, {
        method: 'POST',
        body: { username_or_email, role }
      });
      showToast('Team member added.', 'success');
      input.value = '';
      renderTeamList();
    } catch (err) {}
  });

  // Activity Drawer Trigger
  document.getElementById('openActivityDrawerBtn')?.addEventListener('click', () => {
    renderActivityStream();
    const drawer = new bootstrap.Offcanvas(document.getElementById('activityDrawer'));
    drawer.show();
  });
}
