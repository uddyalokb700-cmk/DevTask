/**
 * Projects Directory & Management Controller
 */

let cachedProjects = [];

async function loadProjects() {
  const grid = document.getElementById('projectsGrid');
  const search = document.getElementById('projectSearchInput').value.trim();
  const isArchived = document.getElementById('filterArchived').checked;

  try {
    let url = `/api/projects/?archived=${isArchived}`;
    if (search) {
      url += `&search=${encodeURIComponent(search)}`;
    }

    const projects = await apiRequest(url);
    cachedProjects = projects;

    if (!projects || projects.length === 0) {
      grid.innerHTML = `
        <div class="col-12 text-center text-muted py-5">
          <div class="mb-3">
            <i class="bi bi-folder-plus fs-1 text-secondary opacity-50"></i>
          </div>
          <h5 class="fw-semibold text-light mb-1">No ${isArchived ? 'archived' : 'active'} projects found</h5>
          <p class="small text-muted mb-3">Create a new project workspace to start organizing tasks.</p>
          ${!isArchived ? `
            <button class="btn btn-devtask-primary btn-sm" data-bs-toggle="modal" data-bs-target="#createProjectModal">
              <i class="bi bi-plus-lg me-1"></i>Create First Project
            </button>
          ` : ''}
        </div>
      `;
      return;
    }

    grid.innerHTML = projects.map(p => {
      const total = p.tasks_count || 0;
      const done = p.completed_tasks_count || 0;
      const pct = total > 0 ? Math.round((done / total) * 100) : 0;
      const role = p.current_user_role || 'MEMBER';
      const isOwner = role === 'OWNER';
      const canManage = isOwner || role === 'MANAGER';

      return `
        <div class="col-md-6 col-xl-4">
          <div class="card-devtask h-100 d-flex flex-column">
            <div class="card-devtask-body flex-grow-1">
              <div class="d-flex justify-content-between align-items-start gap-2 mb-2">
                <h5 class="fw-bold text-light mb-0 text-truncate">
                  <a href="/projects/${p.id}/" class="text-decoration-none text-light hover-accent">
                    ${escapeHtml(p.name)}
                  </a>
                </h5>
                <span class="badge ${isOwner ? 'bg-primary-subtle text-primary border border-primary-subtle' : 'bg-secondary-subtle text-secondary border border-secondary-subtle'} small" style="font-size: 0.72rem;">
                  ${escapeHtml(role)}
                </span>
              </div>

              <p class="text-muted small mb-3 text-truncate-2" style="min-height: 2.4rem;">
                ${escapeHtml(p.description || 'No description provided.')}
              </p>

              <!-- Progress bar -->
              <div class="mb-3">
                <div class="d-flex justify-content-between text-muted small mb-1" style="font-size: 0.75rem;">
                  <span>Tasks: ${done}/${total} completed</span>
                  <span class="fw-semibold text-light">${pct}%</span>
                </div>
                <div class="progress" style="height: 6px; background-color: var(--bg-surface-elevated);">
                  <div class="progress-bar bg-success" role="progressbar" style="width: ${pct}%"></div>
                </div>
              </div>

              <!-- Owner & Created Info -->
              <div class="d-flex align-items-center justify-content-between text-muted small pt-2 border-top border-secondary-subtle" style="font-size: 0.78rem;">
                <div class="d-flex align-items-center gap-2">
                  <div class="avatar-initials" style="width: 24px; height: 24px; font-size: 0.7rem; background-color: ${p.owner?.avatar_color || '#3b82f6'};">
                    ${escapeHtml((p.owner?.username || 'U')[0].toUpperCase())}
                  </div>
                  <span class="text-truncate" style="max-width: 120px;">${escapeHtml(p.owner?.display_name || p.owner?.username)}</span>
                </div>
                <span>Updated ${formatRelativeTime(p.updated_at)}</span>
              </div>
            </div>

            <!-- Footer Actions -->
            <div class="card-devtask-header bg-transparent border-top border-secondary-subtle py-2 px-3">
              <a href="/projects/${p.id}/" class="btn btn-sm btn-devtask-primary py-1 px-3" style="font-size: 0.8rem;">
                <i class="bi bi-kanban me-1"></i>Open Board
              </a>

              <div class="d-flex gap-1 ms-auto">
                ${canManage ? `
                  <button class="btn btn-sm btn-devtask-secondary py-1 px-2" style="font-size: 0.8rem;" title="Edit Project" onclick="openEditProjectModal('${p.id}')">
                    <i class="bi bi-pencil"></i>
                  </button>
                ` : ''}

                ${isOwner ? `
                  <button class="btn btn-sm btn-devtask-secondary py-1 px-2 text-danger" style="font-size: 0.8rem;" title="${p.archived_at ? 'Restore Project' : 'Archive Project'}" onclick="toggleArchiveProject('${p.id}', ${Boolean(p.archived_at)})">
                    <i class="bi bi-${p.archived_at ? 'arrow-counterclockwise text-success' : 'archive'}"></i>
                  </button>
                ` : ''}
              </div>
            </div>
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    grid.innerHTML = `
      <div class="col-12 text-center text-danger py-5">
        <i class="bi bi-exclamation-triangle fs-2 d-block mb-2"></i>
        Failed to load projects. Please try refreshing.
      </div>
    `;
  }
}

function openEditProjectModal(projectId) {
  const project = cachedProjects.find(p => p.id === projectId);
  if (!project) return;

  document.getElementById('editProjectId').value = project.id;
  document.getElementById('editProjectNameInput').value = project.name;
  document.getElementById('editProjectDescInput').value = project.description || '';

  const modal = new bootstrap.Modal(document.getElementById('editProjectModal'));
  modal.show();
}

async function toggleArchiveProject(projectId, isArchived) {
  const action = isArchived ? 'unarchive' : 'archive';
  const confirmMsg = isArchived
    ? 'Restore this project back to active workspaces?'
    : 'Archive this project? It will be hidden from the active view.';

  if (!confirm(confirmMsg)) return;

  try {
    await apiRequest(`/api/projects/${projectId}/archive/`, {
      method: 'POST',
      body: { action }
    });
    showToast(`Project ${action}d successfully.`, 'success');
    loadProjects();
  } catch (err) {
    // Toast handled in apiRequest
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadProjects();

  // Search input with debounce
  const searchInput = document.getElementById('projectSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', debounce(() => loadProjects(), 300));
  }

  // Active / Archived radio toggles
  document.getElementById('filterActive')?.addEventListener('change', () => loadProjects());
  document.getElementById('filterArchived')?.addEventListener('change', () => loadProjects());

  // Create Project Form
  const createForm = document.getElementById('createProjectForm');
  if (createForm) {
    createForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = document.getElementById('projectNameInput').value.trim();
      const description = document.getElementById('projectDescInput').value.trim();

      try {
        const newProj = await apiRequest('/api/projects/', {
          method: 'POST',
          body: { name, description }
        });
        showToast('Project created successfully!', 'success');
        bootstrap.Modal.getInstance(document.getElementById('createProjectModal'))?.hide();
        createForm.reset();
        window.location.href = `/projects/${newProj.id}/`;
      } catch (err) {
        // Handled in apiRequest
      }
    });
  }

  // Edit Project Form
  const editForm = document.getElementById('editProjectForm');
  if (editForm) {
    editForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const projectId = document.getElementById('editProjectId').value;
      const name = document.getElementById('editProjectNameInput').value.trim();
      const description = document.getElementById('editProjectDescInput').value.trim();

      try {
        await apiRequest(`/api/projects/${projectId}/`, {
          method: 'PATCH',
          body: { name, description }
        });
        showToast('Project updated.', 'success');
        bootstrap.Modal.getInstance(document.getElementById('editProjectModal'))?.hide();
        loadProjects();
      } catch (err) {
        // Handled in apiRequest
      }
    });
  }
});
