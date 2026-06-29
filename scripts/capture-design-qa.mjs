import { createRequire } from 'node:module'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'

const require = createRequire('/Users/mima1234/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/package.json')
const { chromium } = require('playwright')

const root = '/Users/mima1234/Documents/AI产品经理/Auto-jianji'
const outDir = path.join(root, 'design-qa-artifacts')
const baseUrl = 'http://127.0.0.1:2001'
const draftId = 'qa_reference_draft'
const previewTaskId = 'qa_reference_task'

const sampleManuscript = `1  大脑如何影响我们的决策？

你是否有过这样的经历：明明知道不应该买，却在情绪低落时下单了很多东西？
或者明明想要好好休息，却因为一时愤怒做了后悔的决定？
这并不是你不够理智，而是情绪正在悄悄影响着你的大脑。

2  情绪与大脑的关系

研究表明，情绪会影响我们大脑中负责决策的区域，改变我们对风险和收益的判断。
例如，在压力状态下，我们的大脑更倾向于选择“即时缓解”的方案，而忽略了长期后果。

3  关键脑区的作用

杏仁核负责识别情绪信号，尤其是恐惧和愤怒。
前额叶皮层负责理性思考、计划和自我控制。
伏隔核与奖励感相关，促使我们追求即时满足。

4  决策的双系统模型

系统 1 快速、自动、情绪化；系统 2 缓慢、理性、深思熟虑。
在多数日常决策中，系统 1 占据主导地位。

5  如何做出更好的决策？

觉察情绪：识别当下的情绪状态。
暂停片刻：给自己几秒钟，避免冲动反应。
理性评估：列出选项的长期收益与风险。
复盘反思：从过去的决策中学习，形成更清晰的判断。

6  为什么我们会被错觉欺骗？

因为大脑不是被动记录世界的摄像机，而是主动预测世界的解释器。
它会把眼睛看到的信息、过去的经验、当下的情绪和环境线索合在一起，快速给出一个“最可能”的答案。
这种机制通常很高效，但在特殊场景下也会让我们误判。

7  让判断更稳的方法

第一，把重要决定从情绪高峰里拿出来。
第二，用文字写下选项，而不是只在脑子里反复想。
第三，给自己一个外部视角，问一句：如果这是朋友的选择，我会怎么建议？

8  总结

好的决策并不是永远冷静，而是知道自己什么时候不够冷静。
理解大脑的默认机制，不是为了否定直觉，而是为了在关键时刻多保留一次选择的空间。`

const draft = {
  draft_id: draftId,
  name: '大脑如何影响我们的决策',
  input_mode: 'script',
  theme: '',
  manuscript: sampleManuscript,
  ratio: '16:9',
  visual_style: '吉卜力',
  text_style: '知识科普',
  voice_type: '',
  voice_name: '',
  voice_speed: 1,
  subtitle_enabled: true,
  created_task_id: '',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

const previewSegments = [
  {
    id: 'qa_seg_1',
    segment_index: 0,
    text: '你有没有过这样的经历：明明眼睛看到的，大脑却告诉你是错的？',
    image_prompt: '一个男孩站在高处眺望海边小镇，蓝天白云，治愈系吉卜力风格。',
    image_url: `${baseUrl}/reference-assets/hq-coastal-boy.jpg`,
    audio_url: `${baseUrl}/reference-assets/hq-coastal-boy.jpg`,
    duration: 7,
  },
  {
    id: 'qa_seg_2',
    segment_index: 1,
    text: '这不是你的问题，而是大脑的默认设置。',
    image_prompt: '可爱的拟人脑袋坐在书桌前阅读，温暖光线，毛毡动画质感。',
    image_url: `${baseUrl}/reference-assets/clean-brain-reading.jpg`,
    audio_url: `${baseUrl}/reference-assets/clean-brain-reading.jpg`,
    duration: 7,
  },
  {
    id: 'qa_seg_3',
    segment_index: 2,
    text: '今天，我们来聊聊视觉错觉背后的认知机制。',
    image_prompt: '水墨山水与古建筑，国风科普画面，安静克制。',
    image_url: `${baseUrl}/reference-assets/clean-ink-mountain.jpg`,
    audio_url: `${baseUrl}/reference-assets/clean-ink-mountain.jpg`,
    duration: 7,
  },
  {
    id: 'qa_seg_4',
    segment_index: 3,
    text: '我们的大脑为了快速处理信息，常常会走捷径。',
    image_prompt: '未来城市与飞行器，明亮科技感，适合科普解释。',
    image_url: `${baseUrl}/reference-assets/clean-future-city.jpg`,
    audio_url: `${baseUrl}/reference-assets/clean-future-city.jpg`,
    duration: 9,
  },
  {
    id: 'qa_seg_5',
    segment_index: 4,
    text: '它会根据经验补全缺失的细节。',
    image_prompt: '女孩在书桌前认真学习，温暖室内光线，动画风格。',
    image_url: `${baseUrl}/reference-assets/clean-girl-study.jpg`,
    audio_url: `${baseUrl}/reference-assets/clean-girl-study.jpg`,
    duration: 9,
  },
  {
    id: 'qa_seg_6',
    segment_index: 5,
    text: '这就导致了，眼见不一定为实。',
    image_prompt: '宇航员站在月球表面，远处是地球，写实科幻风格。',
    image_url: `${baseUrl}/reference-assets/clean-astronaut-moon.jpg`,
    audio_url: `${baseUrl}/reference-assets/clean-astronaut-moon.jpg`,
    duration: 7,
  },
  {
    id: 'qa_seg_7',
    segment_index: 6,
    text: '比如著名的米勒莱尔错觉。',
    image_prompt: '城市街道中的人群和箭头示意，清晰科普画面。',
    image_url: `${baseUrl}/reference-assets/clean-city-street.jpg`,
    audio_url: `${baseUrl}/reference-assets/clean-city-street.jpg`,
    duration: 9,
  },
  {
    id: 'qa_seg_8',
    segment_index: 7,
    text: '理解这些机制，能帮助我们更高效地学习与决策。',
    image_prompt: '蓝色神经网络与数据波形，现代科技可视化。',
    image_url: `${baseUrl}/reference-assets/clean-data-wave.jpg`,
    audio_url: `${baseUrl}/reference-assets/clean-data-wave.jpg`,
    duration: 10,
  },
]

async function main() {
  await mkdir(outDir, { recursive: true })
  const browser = await chromium.launch({
    channel: 'chrome',
    headless: true,
    args: ['--disable-gpu', '--hide-scrollbars'],
  })
  const context = await browser.newContext({ viewport: { width: 1536, height: 1024 } })
  await context.addInitScript((seedDraft) => {
    window.localStorage.setItem('insightcut:project-drafts', JSON.stringify([seedDraft]))
  }, draft)
  const page = await context.newPage()
  await page.route(`**/ai/native/video/kepu/tasks/${previewTaskId}`, async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        task_id: previewTaskId,
        name: '大脑学习机制科普',
        status: 'completed',
        result: {
          theme: '大脑学习机制科普',
          total_duration: 150,
          segments_count: previewSegments.length,
          created_at: new Date().toISOString(),
        },
      }),
    })
  })
  await page.route(`**/ai/native/video/kepu/tasks/${previewTaskId}/segments`, async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(previewSegments) })
  })
  await page.route(`**/ai/native/video/kepu/tasks/${previewTaskId}/assets**`, async (route) => {
    const assets = previewSegments.map((segment) => ({
      asset_id: `asset_${segment.segment_index}`,
      asset_type: 'image',
      segment_index: segment.segment_index,
      url: segment.image_url,
      file_url: segment.image_url,
      has_file: true,
      label: `分镜 ${segment.segment_index + 1}`,
    }))
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(assets) })
  })

  const captures = [
    ['current-home-manuscript.png', `${baseUrl}/manuscript/${draftId}`, '.manuscript-page'],
    ['current-assets.png', `${baseUrl}/assets`, '.asset-page'],
    ['current-production.png', `${baseUrl}/production/${draftId}`, '.production-page'],
    ['current-settings.png', `${baseUrl}/settings`, '.settings-view'],
  ]

  for (const [file, url, selector] of captures) {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 })
    await page.waitForSelector(selector, { timeout: 20000 })
    await page.waitForTimeout(900)
    await page.screenshot({ path: path.join(outDir, file), fullPage: false })
  }

  await page.goto(`${baseUrl}/preview/${previewTaskId}`, { waitUntil: 'domcontentloaded', timeout: 20000 })
  await page.waitForSelector('.preview-page', { timeout: 20000 })
  await page.waitForTimeout(1200)
  await page.screenshot({ path: path.join(outDir, 'current-preview.png'), fullPage: false })

  await browser.close()
  console.log(`Captured QA screenshots in ${outDir}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
