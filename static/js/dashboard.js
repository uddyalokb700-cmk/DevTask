/**
 * Dashboard Client Controller & Analytics Charts
 */

let statusChartInstance = null;
let priorityChartInstance = null;

async function loadDashboardData() {
  const kpiActiveProjects = document.getElementById('kpiActiveProjects');
  const kpiOpenTasks = document.getElementById('kpiOpenTasks');
  const kpiMyTasks = document.getElementById('kpiMyTasks');
  const kpiOverdueTasks = document.getElementById('kpiOverdueTasks');
  const completionText = document.getElementById('completionRateText');
  const deadlinesTbody = document.getElementById('upcomingDeadlinesTbody');
  const projectsTbody = document.getElementById('recentProjectsTbody');

  try {
    const data = await apiRequest('/api/projects/dashboard-stats/');
    const metrics = data.metrics || {};

    // 1. Update KPI Cards
    if (kpiActiveProjects) kpiActiveProjects.textContent = metrics.active_projects ?? 0;
    if (kpiOpenTasks) kpiOpenTasks.textContent = metrics.open_tasks ?? 0;
    if (kpiMyTasks) kpiMyTasks.textContent = metrics.my_open_tasks ?? 0;
    if (kpiOverdueTasks) kpiOverdueTasks.textContent = metrics.overdue_tasks ?? 0;
    if (completionText) completionText.textContent = `Completion: ${metrics.completion_percentage ?? 0}%`;

    // 2. Status Chart & Legend Counts
    const statusDist = data.status_distribution || { TODO: 0, IN_PROGRESS: 0, DONE: 0 };
    document.getElementById('chartTodoCount').textContent = statusDist.TODO || 0;
    document.getElementById('chartInProgressCount').textContent = statusDist.IN_PROGRESS || 0;
    document.getElementById('chartDoneCount').textContent = statusDist.DONE || 0;

    renderStatusChart(statusDist);

    // 3. Priority Chart
    const prioDist = data.priority_distribution || { LOW: 0, MEDIUM: 0, HIGH: 0, URGENT: 0 };
    renderPriorityChart(prioDist);

    // 4. Render Upcoming Deadlines Table
    const upcoming = data.upcoming_deadlines || [];
    if (deadlinesTbody) {
      if (upcoming.length === 0) {
        deadlinesTbody.innerHTML = `
          <tr>
            <td colspan="4" class="text-center text-muted py-4 small">
              <i class="bi bi-calendar-check d-block mb-1 fs-5"></i>
              No upcoming task deadlines scheduled.
            </td>
          </tr>
        `;
      } else {
        deadlinesTbody.innerHTML = upcoming.map(t => {
          const prioLower = (t.priority || 'medium').toLowerCase();
          return `
            <tr>
              <td class="ps-3 py-2">
                <a href="/projects/${t.project_id}/" class="text-decoration-none fw-semibold text-light small text-truncate d-inline-block" style="max-width: 220px;">
                  ${escapeHtml(t.title)}
                </a>
              </td>
              <td class="py-2 text-muted small">${escapeHtml(t.project_name)}</td>
              <td class="py-2 small">
                <span class="badge-prio ${prioLower}">${escapeHtml(t.priority)}</span>
                <span class="text-secondary ms-1">${escapeHtml(t.due_date)}</span>
              </td>
              <td class="pe-3 py-2 text-end text-muted small">${escapeHtml(t.assignee_name)}</td>
            </tr>
          `;
        }).join('');
      }
    }

    // 5. Render Recent Projects Table
    const recentProjects = data.recent_projects || [];
    if (projectsTbody) {
      if (recentProjects.length === 0) {
        projectsTbody.innerHTML = `
          <tr>
            <td colspan="3" class="text-center text-muted py-4 small">
              <i class="bi bi-folder-x d-block mb-1 fs-5"></i>
              No active projects yet.
            </td>
          </tr>
        `;
      } else {
        projectsTbody.innerHTML = recentProjects.map(p => {
          const total = p.tasks_count || 0;
          const completed = p.completed_tasks_count || 0;
          const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
          return `
            <tr>
              <td class="ps-3 py-2">
                <a href="/projects/${p.id}/" class="text-decoration-none fw-semibold text-light small">
                  ${escapeHtml(p.name)}
                </a>
                <div class="text-muted" style="font-size: 0.75rem;">${total} tasks total</div>
              </td>
              <td class="py-2" style="min-width: 140px;">
                <div class="d-flex align-items-center gap-2">
                  <div class="progress flex-grow-1" style="height: 6px; background-color: var(--bg-surface-elevated);">
                    <div class="progress-bar bg-success" role="progressbar" style="width: ${pct}%"></div>
                  </div>
                  <span class="small text-muted" style="font-size: 0.75rem;">${pct}%</span>
                </div>
              </td>
              <td class="pe-3 py-2 text-end">
                <a href="/projects/${p.id}/" class="btn btn-sm btn-devtask-secondary py-1 px-2" style="font-size: 0.78rem;">
                  Open Board →
                </a>
              </td>
            </tr>
          `;
        }).join('');
      }
    }

  } catch (err) {
    console.error('Failed to load dashboard metrics:', err);
    showToast('Failed to load dashboard data. Retrying...', 'error');
  }
}

function renderStatusChart(statusDist) {
  const ctx = document.getElementById('statusChart');
  if (!ctx) return;

  if (statusChartInstance) {
    statusChartInstance.destroy();
  }

  const values = [statusDist.TODO || 0, statusDist.IN_PROGRESS || 0, statusDist.DONE || 0];
  const allZero = values.every(v => v === 0);

  statusChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['To Do', 'In Progress', 'Done'],
      datasets: [{
        data: allZero ? [1, 1, 1] : values,
        backgroundColor: allZero
          ? ['rgba(255,255,255,0.05)', 'rgba(255,255,255,0.05)', 'rgba(255,255,255,0.05)']
          : ['#94a3b8', '#38bdf8', '#10b981'],
        borderWidth: 2,
        borderColor: '#10131b',
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '72%',
      plugins: {
        legend: { display: false },
        tooltip: {
          enabled: !allZero,
          callbacks: {
            label: (item) => ` ${item.label}: ${item.raw} tasks`
          }
        }
      }
    }
  });
}

function renderPriorityChart(prioDist) {
  const ctx = document.getElementById('priorityChart');
  if (!ctx) return;

  if (priorityChartInstance) {
    priorityChartInstance.destroy();
  }

  priorityChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Low', 'Medium', 'High', 'Urgent'],
      datasets: [{
        data: [
          prioDist.LOW || 0,
          prioDist.MEDIUM || 0,
          prioDist.HIGH || 0,
          prioDist.URGENT || 0
        ],
        backgroundColor: ['#64748b', '#3b82f6', '#f59e0b', '#ef4444'],
        borderRadius: 6,
        borderSkipped: false
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#9ca3af', font: { size: 11 } }
        },
        y: {
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: { color: '#9ca3af', font: { size: 10 }, stepSize: 1 },
          beginAtZero: true
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (item) => ` ${item.raw} tasks`
          }
        }
      }
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  loadDashboardData();

  const refreshBtn = document.getElementById('refreshDashboardBtn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      refreshBtn.querySelector('i').classList.add('spin-animation');
      loadDashboardData().finally(() => {
        refreshBtn.querySelector('i').classList.remove('spin-animation');
        showToast('Dashboard updated.', 'info');
      });
    });
  }
});
