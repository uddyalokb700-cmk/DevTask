-- ==============================================================================
-- DevTask PostgreSQL Query Execution Plans & Buffer Usage
-- Execute: psql -d devtask -f loadtests/explain_postgres.sql
-- ==============================================================================

-- 1. Project List Query with Database Aggregations and User Filtering
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT DISTINCT
    p.id, p.name, p.description, p.owner_id, p.created_at, p.updated_at, p.archived_at,
    COUNT(DISTINCT pm.id) AS members_count,
    COUNT(DISTINCT t.id) AS tasks_count,
    COUNT(DISTINCT t.id) FILTER (WHERE t.status = 'DONE') AS completed_tasks_count,
    u.id, u.username, up.display_name, up.avatar_color
FROM projects_project p
INNER JOIN auth_user u ON (p.owner_id = u.id)
LEFT OUTER JOIN projects_projectmembership pm ON (p.id = pm.project_id)
LEFT OUTER JOIN tasks_task t ON (p.id = t.project_id)
LEFT OUTER JOIN accounts_userprofile up ON (u.id = up.user_id)
WHERE (p.owner_id = 1 OR pm.user_id = 1) AND p.archived_at IS NULL
GROUP BY p.id, u.id, up.id
ORDER BY p.updated_at DESC;

-- 2. Paginated Tasks with Composite Index and Subquery Comments Count
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT
    t.id, t.project_id, t.title, t.description, t.status, t.priority,
    t.created_by_id, t.assignee_id, t.due_date, t.position, t.created_at, t.updated_at,
    COALESCE((
        SELECT COUNT(c.id)
        FROM tasks_taskcomment c
        WHERE c.task_id = t.id
    ), 0) AS comments_count,
    p.name AS project_name,
    u.username AS creator_username,
    a.username AS assignee_username
FROM tasks_task t
INNER JOIN projects_project p ON (t.project_id = p.id)
INNER JOIN auth_user u ON (t.created_by_id = u.id)
LEFT OUTER JOIN auth_user a ON (t.assignee_id = a.id)
WHERE t.project_id = (SELECT id FROM projects_project LIMIT 1)
ORDER BY t.position ASC, t.created_at DESC
LIMIT 20 OFFSET 0;

-- 3. Filtered Tasks (Status=TODO, Priority=HIGH using idx_task_status_prio)
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT
    t.id, t.project_id, t.title, t.status, t.priority, t.due_date
FROM tasks_task t
WHERE t.status = 'TODO' AND t.priority = 'HIGH'
ORDER BY t.position ASC
LIMIT 20;

-- 4. Dashboard Aggregation Across Projects
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT
    COUNT(t.id) AS total_tasks,
    COUNT(CASE WHEN t.status = 'TODO' THEN 1 END) AS todo_tasks,
    COUNT(CASE WHEN t.status = 'IN_PROGRESS' THEN 1 END) AS in_progress_tasks,
    COUNT(CASE WHEN t.status = 'DONE' THEN 1 END) AS done_tasks,
    COUNT(CASE WHEN t.due_date < CURRENT_DATE AND t.status != 'DONE' THEN 1 END) AS overdue_tasks
FROM tasks_task t
INNER JOIN projects_project p ON (t.project_id = p.id)
WHERE p.archived_at IS NULL AND (p.owner_id = 1 OR EXISTS (
    SELECT 1 FROM projects_projectmembership pm WHERE pm.project_id = p.id AND pm.user_id = 1
));
