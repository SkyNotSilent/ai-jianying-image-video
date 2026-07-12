export function getProjectPrimaryAction(project = {}) {
  if (project.type === 'draft') return 'draft'
  if (project.status === 'interrupted') return 'resume'
  if (project.status === 'processing') return 'progress'
  return 'preview'
}

export function getDeleteConfirmation(project = {}) {
  if (project.type === 'draft') {
    return {
      title: '删除草稿',
      message: `确认删除“${project.name || '未命名文稿'}”的本地文稿草稿？此操作不可恢复，但不会删除后端生成项目。`,
      confirmLabel: '删除草稿',
    }
  }

  return {
    title: '删除项目',
    message: `确认永久删除“${project.name || '未命名项目'}”？项目文稿、图片、配音、视频和剪映草稿都会一并删除，此操作不可恢复。`,
    confirmLabel: '永久删除',
  }
}

export function getDeletionIssueCount(result = {}) {
  const report = result?.deletion_report || {}
  const failed = Array.isArray(report.failed_paths) ? report.failed_paths.length : 0
  const skipped = Array.isArray(report.skipped_paths) ? report.skipped_paths.length : 0
  return failed + skipped
}
