/**
 * 工具函数
 * 时间格式化、进度计算、步骤名称映射
 */

/**
 * 格式化时长
 * @param {number} seconds - 秒数
 * @returns {string} 格式化后的时长，如 "2分30秒"
 */
export function formatDuration(seconds) {
  if (!seconds || seconds < 0) return '0秒'

  const minutes = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)

  if (minutes === 0) {
    return `${secs}秒`
  }

  return `${minutes}分${secs}秒`
}

/**
 * 格式化时间戳
 * @param {string} iso - ISO 格式时间字符串
 * @returns {string} 格式化后的时间，如 "2026-04-16 15:30"
 */
export function formatTimestamp(iso) {
  if (!iso) return ''

  const date = new Date(iso)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')

  return `${year}-${month}-${day} ${hours}:${minutes}`
}

/**
 * 步骤权重映射
 */
const STEP_WEIGHTS = {
  text_generation: 10,
  image_prompt_generation: 15,
  voiceover_generation: 20,
  image_generation: 25,
  draft_building: 30
}

/**
 * 计算总进度百分比
 * @param {Array} steps - 步骤数组
 * @returns {number} 总进度百分比 (0-100)
 */
export function calculateProgress(steps) {
  if (!steps || steps.length === 0) return 0

  let totalProgress = 0

  steps.forEach(step => {
    const weight = STEP_WEIGHTS[step.name] || 0

    if (step.status === 'completed') {
      totalProgress += weight
    } else if (step.status === 'processing' && step.progress && step.total) {
      const stepProgress = (step.progress / step.total) * weight
      totalProgress += stepProgress
    }
  })

  return Math.min(Math.round(totalProgress), 100)
}

/**
 * 步骤名称映射（英文 -> 中文）
 */
const STEP_LABELS = {
  text_generation: '脚本改写',
  image_prompt_generation: '生成画面描述',
  voiceover_generation: '配音生成',
  image_generation: '图像生成',
  draft_building: '草稿构建'
}

/**
 * 获取步骤的中文名称
 * @param {string} stepName - 步骤英文名称
 * @returns {string} 步骤中文名称
 */
export function getStepLabel(stepName) {
  return STEP_LABELS[stepName] || stepName
}

/**
 * 获取步骤权重
 * @param {string} stepName - 步骤名称
 * @returns {number} 步骤权重
 */
export function getStepWeight(stepName) {
  return STEP_WEIGHTS[stepName] || 0
}
