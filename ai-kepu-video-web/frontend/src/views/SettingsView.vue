<template>
  <div class="settings-view">
    <NavBar active-tab="settings" @navigate="handleNavigate" />

    <main class="settings-main">
      <div class="settings-header">
        <h1>API 配置</h1>
        <p>先完成生文、生图和配音 API 配置，再进入视频生产。</p>
      </div>

      <div v-loading="loading" element-loading-text="加载中..." class="settings-content">
        <section v-if="!loading" class="readiness-summary">
          <div v-for="item in readinessItems" :key="item.label" :class="['ready-item', item.ready ? 'ok' : 'warn']">
            <span></span>
            <div>
              <strong>{{ item.label }}</strong>
              <small>{{ item.desc }}</small>
            </div>
          </div>
          <button type="button" class="secondary-btn" @click="router.back()">返回生产</button>
        </section>

        <div v-if="!loading" class="settings-grid">
        <section class="settings-card">
          <div class="card-header">
            <h2>生文模型</h2>
            <span class="card-tag">LLM</span>
          </div>

          <label class="field">
            <span>协议类型</span>
            <div class="protocol-group">
              <button
                type="button"
                class="protocol-btn"
                :class="{ active: form.llm.protocol === 'anthropic' }"
                @click="form.llm.protocol = 'anthropic'"
              >Anthropic 兼容</button>
              <button
                type="button"
                class="protocol-btn"
                :class="{ active: form.llm.protocol === 'openai' }"
                @click="form.llm.protocol = 'openai'"
              >OpenAI 兼容</button>
            </div>
          </label>

          <label class="field">
            <span>API Base URL</span>
            <input v-model.trim="form.llm.base_url" class="text-input" placeholder="https://token-plan-sgp.xiaomimimo.com/v1" />
          </label>

          <label class="field">
            <span>API Key</span>
            <input v-model="form.llm.api_key" class="text-input" type="password" autocomplete="off" placeholder="sk-..." />
          </label>

          <label class="field">
            <span>Model</span>
            <div class="model-picker">
              <input v-model.trim="form.llm.model" class="text-input" placeholder="mimo-v2.5-pro" />
              <button class="secondary-btn compact-btn" :disabled="modelLoading.llm" @click="loadModelOptions('llm')">
                <el-icon v-if="modelLoading.llm" class="is-loading"><Loading /></el-icon>
                <span>{{ modelLoading.llm ? '获取中' : '获取模型列表' }}</span>
              </button>
            </div>
            <select v-if="modelOptions.llm.length" v-model="form.llm.model" class="text-input model-select">
              <option value="">请选择模型</option>
              <option v-for="model in modelOptions.llm" :key="model.id" :value="model.id">{{ model.label }}</option>
            </select>
          </label>
        </section>

        <section class="settings-card">
          <div class="card-header">
            <h2>生图模型</h2>
            <span class="card-tag">Image</span>
          </div>

          <label class="field">
            <span>API URL</span>
            <input v-model.trim="form.image.api_url" class="text-input" placeholder="https://api.example.com/v1/images/generations" />
          </label>

          <label class="field">
            <span>API Key</span>
            <input v-model="form.image.api_key" class="text-input" type="password" autocomplete="off" placeholder="sk-..." />
          </label>

          <label class="field">
            <span>Model</span>
            <div class="model-picker">
              <input v-model.trim="form.image.model" class="text-input" placeholder="agnes-image-2.1-flash" />
              <button class="secondary-btn compact-btn" :disabled="modelLoading.image" @click="loadModelOptions('image')">
                <el-icon v-if="modelLoading.image" class="is-loading"><Loading /></el-icon>
                <span>{{ modelLoading.image ? '获取中' : '获取模型列表' }}</span>
              </button>
            </div>
            <select v-if="modelOptions.image.length" v-model="form.image.model" class="text-input model-select">
              <option value="">请选择模型</option>
              <option v-for="model in modelOptions.image" :key="model.id" :value="model.id">{{ model.label }}</option>
            </select>
          </label>

          <label class="field">
            <span>图片尺寸</span>
            <select v-model="form.image.size" class="text-input">
              <option value="auto">自动匹配画幅</option>
              <option value="1024x1024">1024x1024</option>
              <option value="1536x1024">1536x1024</option>
              <option value="1024x1536">1024x1536</option>
              <option value="1792x1024">1792x1024</option>
              <option value="1024x1792">1024x1792</option>
              <option value="1920x1080">1920x1080</option>
              <option value="1080x1920">1080x1920</option>
            </select>
          </label>
        </section>

        <section class="settings-card tts-card">
          <div class="card-header">
            <h2>配音模型</h2>
            <span class="card-tag">{{ form.tts.provider === 'mimo' ? 'MiMo TTS' : 'Doubao TTS' }}</span>
          </div>

          <label class="field provider-field">
            <span>Provider</span>
            <div class="protocol-group">
              <button
                type="button"
                class="protocol-btn"
                :class="{ active: form.tts.provider === 'doubao' }"
                @click="form.tts.provider = 'doubao'"
              >豆包 TTS</button>
              <button
                type="button"
                class="protocol-btn"
                :class="{ active: form.tts.provider === 'mimo' }"
                @click="useMimoPreset"
              >小米 MiMo TTS</button>
            </div>
          </label>

          <div class="fields-row">
            <label v-if="form.tts.provider === 'doubao'" class="field auth-method-field">
              <span>豆包认证方式</span>
              <div class="protocol-group">
                <button
                  type="button"
                  class="protocol-btn"
                  :class="{ active: form.tts.auth_method === 'access_token' }"
                  @click="form.tts.auth_method = 'access_token'"
                >AppID / Access Token</button>
                <button
                  type="button"
                  class="protocol-btn"
                  :class="{ active: form.tts.auth_method === 'api_key' }"
                  @click="form.tts.auth_method = 'api_key'"
                >API Key</button>
              </div>
              <small class="field-help">豆包旧版在线合成使用 AppID/Access Token；火山新版语音接口也支持 API Key 鉴权。</small>
            </label>

            <label v-if="form.tts.provider === 'doubao'" class="field">
              <span>API URL</span>
              <input v-model.trim="form.tts.api_url" class="text-input" placeholder="https://openspeech.bytedance.com/api/v1/tts" />
            </label>

            <label v-if="form.tts.provider === 'doubao' && form.tts.auth_method === 'access_token'" class="field">
              <span>App ID</span>
              <input v-model.trim="form.tts.appid" class="text-input" autocomplete="off" placeholder="豆包 TTS App ID" />
            </label>

            <label v-if="form.tts.provider === 'doubao' && form.tts.auth_method === 'access_token'" class="field">
              <span>Access Token</span>
              <input v-model="form.tts.token" class="text-input" type="password" autocomplete="off" placeholder="豆包语音控制台 Access Token" />
            </label>

            <label v-if="form.tts.provider === 'doubao' && form.tts.auth_method === 'api_key'" class="field">
              <span>API Key</span>
              <input v-model="form.tts.api_key" class="text-input" type="password" autocomplete="off" placeholder="火山控制台 API Key" />
            </label>

            <label v-if="form.tts.provider === 'doubao'" class="field">
              <span>Cluster</span>
              <input v-model.trim="form.tts.cluster" class="text-input" placeholder="volcano_tts" />
              <small class="field-help">旧版在线合成通常为 volcano_tts；如果使用新版资源，请按控制台或接口文档填写对应资源/集群。</small>
            </label>

            <label v-if="form.tts.provider === 'doubao'" class="field">
              <span>默认音色 ID</span>
              <input v-model.trim="form.tts.default_voice" class="text-input" placeholder="zh_male_jieshuoxiaoming_moon_bigtts" />
            </label>

            <template v-else>
              <label class="field">
                <span>Base URL</span>
                <input v-model.trim="form.tts.mimo.base_url" class="text-input" placeholder="https://token-plan-sgp.xiaomimimo.com/v1" />
              </label>

              <label class="field">
                <span>API Key</span>
                <input v-model="form.tts.mimo.api_key" class="text-input" type="password" autocomplete="off" placeholder="小米 Token Plan API Key" />
              </label>

              <label class="field">
                <span>Model</span>
                <input v-model.trim="form.tts.mimo.model" class="text-input" placeholder="mimo-v2.5-tts" />
              </label>

              <label class="field">
                <span>默认音色</span>
                <select v-model="form.tts.mimo.default_voice" class="text-input">
                  <option v-for="voice in mimoVoices" :key="voice.id" :value="voice.id">{{ voice.name }}</option>
                </select>
              </label>

              <label class="field">
                <span>音频格式</span>
                <input v-model.trim="form.tts.mimo.format" class="text-input" placeholder="wav" />
                <small class="field-help">小米 MiMo TTS 通过 /v1/chat/completions 返回 message.audio.data 的 base64 音频。</small>
              </label>

              <label class="field">
                <span>风格指令</span>
                <input v-model.trim="form.tts.mimo.style_prompt" class="text-input" placeholder="自然清晰，适合中文短视频旁白。" />
              </label>
            </template>
          </div>

          <div class="tts-test-row">
            <button type="button" class="secondary-btn" :disabled="testingTts" @click="testTts">
              <el-icon v-if="testingTts" class="is-loading"><Loading /></el-icon>
              <span>{{ testingTts ? '测试中' : '测试配音配置' }}</span>
            </button>
            <audio v-if="ttsTestUrl" :src="ttsTestUrl" controls></audio>
          </div>
        </section>

        <section class="settings-card runtime-card">
          <div class="card-header">
            <h2>生成并发</h2>
            <span class="card-tag">Runtime</span>
          </div>

          <div class="fields-row">
            <label class="field">
              <span>配音并发</span>
              <input v-model.number="form.generation.tts_concurrency" class="text-input" type="number" min="1" max="8" step="1" />
              <small class="field-help">默认 1。调高会更快，但更容易触发豆包限流。</small>
            </label>

            <label class="field">
              <span>生图并发</span>
              <input v-model.number="form.generation.image_concurrency" class="text-input" type="number" min="1" max="1" step="1" />
              <small class="field-help">当前 Agnes 免费限速按 20 RPM 处理，生图并发固定为 1。</small>
            </label>
          </div>
        </section>
        </div>

        <div v-if="!loading" class="settings-actions">
          <button class="secondary-btn" :disabled="saving" @click="loadConfig">重置</button>
          <button class="primary-btn" :disabled="saving" @click="saveConfig">
            <el-icon v-if="saving" class="is-loading" style="margin-right: 8px;"><Loading /></el-icon>
            <span>保存配置</span>
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { fetchConfigModels, getConfig, testTtsConfig, updateConfig } from '../api/task'
import NavBar from '../components/NavBar.vue'

const router = useRouter()
const loading = ref(true)
const saving = ref(false)
const testingTts = ref(false)
const ttsTestUrl = ref('')
const modelLoading = ref({ llm: false, image: false })
const modelOptions = ref({ llm: [], image: [] })
const mimoPreset = {
  base_url: 'https://token-plan-sgp.xiaomimimo.com/v1',
  model: 'mimo-v2.5-tts',
  default_voice: '冰糖',
  format: 'wav',
  style_prompt: '自然清晰，适合中文短视频旁白。',
}
const mimoVoices = [
  { id: 'mimo_default', name: 'MiMo 默认' },
  { id: '冰糖', name: '冰糖 · 女声' },
  { id: '茉莉', name: '茉莉 · 女声' },
  { id: '苏打', name: '苏打 · 男声' },
  { id: '白桦', name: '白桦 · 男声' },
  { id: 'Mia', name: 'Mia · English Female' },
  { id: 'Chloe', name: 'Chloe · English Female' },
  { id: 'Milo', name: 'Milo · English Male' },
  { id: 'Dean', name: 'Dean · English Male' },
]
const form = ref({
  llm: {
    base_url: '',
    api_key: '',
    model: '',
    protocol: 'openai',
  },
  image: {
    api_url: '',
    api_key: '',
    model: '',
    size: 'auto',
  },
  tts: {
    provider: 'doubao',
    auth_method: 'access_token',
    api_url: '',
    appid: '',
    token: '',
    api_key: '',
    cluster: 'volcano_tts',
    default_voice: '',
    mimo: {
      ...mimoPreset,
      api_key: '',
    },
  },
  generation: {
    tts_concurrency: 1,
    image_concurrency: 1,
  },
})

const llmReady = computed(() => Boolean(form.value.llm.base_url && form.value.llm.api_key && form.value.llm.model))
const imageReady = computed(() => Boolean(form.value.image.api_url && form.value.image.api_key && form.value.image.model))
const ttsReady = computed(() => {
  const tts = form.value.tts
  if (tts.provider === 'mimo') {
    return Boolean(tts.mimo.base_url && tts.mimo.api_key && tts.mimo.model && tts.mimo.default_voice)
  }
  if (tts.auth_method === 'api_key') {
    return Boolean(tts.api_url && tts.api_key && tts.cluster && tts.default_voice)
  }
  return Boolean(tts.api_url && tts.appid && tts.token && tts.cluster && tts.default_voice)
})
const readinessItems = computed(() => [
  {
    label: '生文 API',
    ready: llmReady.value,
    desc: llmReady.value ? `${form.value.llm.model} 已填写` : '缺少 Base URL、API Key 或模型名',
  },
  {
    label: '生图 API',
    ready: imageReady.value,
    desc: imageReady.value ? `${form.value.image.model} 已填写` : '缺少 API URL、API Key 或模型名',
  },
  {
    label: 'TTS API',
    ready: ttsReady.value,
    desc: ttsReady.value ? `${form.value.tts.provider === 'mimo' ? 'MiMo' : '豆包'} 已填写` : '缺少配音 provider 的必要配置',
  },
])

onMounted(loadConfig)

function handleNavigate(tab) {
  if (tab === 'settings') return
  if (tab === 'library') {
    router.push('/assets')
    return
  }
  router.push('/')
}

async function loadConfig() {
  loading.value = true
  try {
    const config = await getConfig()
    form.value = {
      llm: {
        base_url: config?.llm?.base_url || '',
        api_key: config?.llm?.api_key || '',
        model: config?.llm?.model || '',
        protocol: config?.llm?.protocol || 'openai',
      },
      image: {
        api_url: config?.image?.api_url || '',
        api_key: config?.image?.api_key || '',
        model: config?.image?.model || '',
        size: config?.image?.size || 'auto',
      },
      tts: {
        provider: config?.tts?.provider || 'doubao',
        auth_method: config?.tts?.auth_method || 'access_token',
        api_url: config?.tts?.api_url || '',
        appid: config?.tts?.appid || '',
        token: config?.tts?.token || '',
        api_key: config?.tts?.api_key || '',
        cluster: config?.tts?.cluster || 'volcano_tts',
        default_voice: config?.tts?.default_voice || '',
        mimo: normalizeMimoConfig(config?.tts?.mimo),
      },
      generation: {
        tts_concurrency: normalizeConcurrency(config?.generation?.tts_concurrency),
        image_concurrency: normalizeImageConcurrency(config?.generation?.image_concurrency),
      },
    }
  } catch (error) {
    console.error('加载 API 配置失败:', error)
    ElMessage.error('加载 API 配置失败')
  } finally {
    loading.value = false
  }
}

async function loadModelOptions(type) {
  const isImage = type === 'image'
  const payload = isImage
    ? {
        protocol: 'openai',
        base_url: form.value.image.api_url,
        api_key: form.value.image.api_key,
      }
    : {
        protocol: form.value.llm.protocol || 'openai',
        base_url: form.value.llm.base_url,
        api_key: form.value.llm.api_key,
      }

  if (!payload.base_url?.trim()) { ElMessage.warning(isImage ? '请先填写生图 API URL' : '请先填写生文 Base URL'); return }
  if (!payload.api_key?.trim()) { ElMessage.warning(isImage ? '请先填写生图 API Key' : '请先填写生文 API Key'); return }

  modelLoading.value[type] = true
  try {
    const result = await fetchConfigModels(payload)
    modelOptions.value[type] = result?.models || []
    if (!modelOptions.value[type].length) {
      ElMessage.warning('没有获取到可选模型')
      return
    }
    if (!form.value[type].model && modelOptions.value[type][0]?.id) {
      form.value[type].model = modelOptions.value[type][0].id
    }
    ElMessage.success(`已获取 ${modelOptions.value[type].length} 个模型`)
  } catch (error) {
    console.error('获取模型列表失败:', error)
    ElMessage.error('获取模型列表失败')
  } finally {
    modelLoading.value[type] = false
  }
}

async function saveConfig() {
  if (!form.value.llm.base_url.trim()) { ElMessage.warning('请输入生文 Base URL'); return }
  if (!form.value.llm.api_key.trim()) { ElMessage.warning('请输入生文 API Key'); return }
  if (!form.value.llm.model.trim()) { ElMessage.warning('请输入生文模型'); return }
  if (!form.value.image.api_url.trim()) { ElMessage.warning('请输入生图 API URL'); return }
  if (!form.value.image.api_key.trim()) { ElMessage.warning('请输入生图 API Key'); return }
  if (!form.value.image.model.trim()) { ElMessage.warning('请输入生图模型'); return }
  if (form.value.tts.provider === 'mimo') {
    if (!form.value.tts.mimo.base_url.trim()) { ElMessage.warning('请输入小米 MiMo Base URL'); return }
    if (!form.value.tts.mimo.api_key.trim()) { ElMessage.warning('请输入小米 MiMo API Key'); return }
    if (!form.value.tts.mimo.model.trim()) { ElMessage.warning('请输入小米 MiMo TTS 模型'); return }
    if (!form.value.tts.mimo.default_voice.trim()) { ElMessage.warning('请选择小米默认音色'); return }
    if (!form.value.tts.mimo.format.trim()) { ElMessage.warning('请输入小米音频格式'); return }
  } else {
    if (!form.value.tts.api_url.trim()) { ElMessage.warning('请输入 TTS API URL'); return }
    if (form.value.tts.auth_method === 'api_key') {
      if (!form.value.tts.api_key.trim()) { ElMessage.warning('请输入豆包 API Key'); return }
    } else {
      if (!form.value.tts.appid.trim()) { ElMessage.warning('请输入 TTS App ID'); return }
      if (!form.value.tts.token.trim()) { ElMessage.warning('请输入豆包 Access Token'); return }
    }
    if (!form.value.tts.cluster.trim()) { ElMessage.warning('请输入 TTS Cluster'); return }
    if (!form.value.tts.default_voice.trim()) { ElMessage.warning('请输入默认音色'); return }
  }
  form.value.generation.tts_concurrency = normalizeConcurrency(form.value.generation.tts_concurrency)
  form.value.generation.image_concurrency = normalizeImageConcurrency(form.value.generation.image_concurrency)

  saving.value = true
  try {
    const saved = await updateConfig(form.value)
    form.value = {
      ...saved,
      generation: {
        ...(saved?.generation || {}),
        image_concurrency: 1,
      },
    }
    ElMessage.success('配置已保存')
  } catch (error) {
    console.error('保存 API 配置失败:', error)
    ElMessage.error('保存 API 配置失败')
  } finally {
    saving.value = false
  }
}

async function testTts() {
  ttsTestUrl.value = ''
  if (form.value.tts.provider === 'mimo') {
    if (!form.value.tts.mimo.base_url.trim() || !form.value.tts.mimo.api_key.trim() || !form.value.tts.mimo.model.trim()) {
      ElMessage.warning('请先补齐小米 MiMo TTS 配置')
      return
    }
  } else if (form.value.tts.auth_method === 'api_key') {
    if (!form.value.tts.api_url.trim() || !form.value.tts.api_key.trim() || !form.value.tts.default_voice.trim()) {
      ElMessage.warning('请先补齐豆包 API Key、API URL 和默认音色')
      return
    }
  } else if (!form.value.tts.api_url.trim() || !form.value.tts.appid.trim() || !form.value.tts.token.trim() || !form.value.tts.default_voice.trim()) {
    ElMessage.warning('请先补齐豆包 AppID、Access Token、API URL 和默认音色')
    return
  }

  testingTts.value = true
  try {
    const result = await testTtsConfig({
      tts: form.value.tts,
      voice_type: form.value.tts.provider === 'mimo' ? form.value.tts.mimo.default_voice : form.value.tts.default_voice,
      text: 'InsightCut 配音配置测试成功。',
    })
    ttsTestUrl.value = result?.url || ''
    ElMessage.success('TTS 配置测试通过')
  } catch (error) {
    console.error('TTS 配置测试失败:', error)
    ElMessage.error(error?.response?.data?.detail || 'TTS 配置测试失败')
  } finally {
    testingTts.value = false
  }
}

function normalizeConcurrency(value) {
  const parsed = Number.parseInt(value, 10)
  if (!Number.isFinite(parsed)) return 1
  return Math.min(8, Math.max(1, parsed))
}

function normalizeImageConcurrency() {
  return 1
}

function normalizeMimoConfig(config = {}) {
  return {
    ...mimoPreset,
    api_key: '',
    ...(config || {}),
  }
}

function useMimoPreset() {
  const current = form.value.tts.mimo || {}
  form.value.tts.provider = 'mimo'
  form.value.tts.mimo = {
    ...mimoPreset,
    ...current,
    api_key: current.api_key || form.value.llm.api_key || '',
    base_url: current.base_url || mimoPreset.base_url,
    model: current.model || mimoPreset.model,
    default_voice: current.default_voice || mimoPreset.default_voice,
    format: current.format || mimoPreset.format,
    style_prompt: current.style_prompt || mimoPreset.style_prompt,
  }
}
</script>

<style scoped>
.settings-view { min-height: 100vh; background: var(--color-bg); display: flex; flex-direction: column; }

.settings-main { flex: 1; width: min(1120px, calc(100% - 48px)); margin: 0 auto; padding: 36px 0 48px; }
.settings-header { margin-bottom: 24px; }
.settings-header h1 { font-size: 28px; line-height: 1.2; margin-bottom: 8px; color: var(--color-text); }
.settings-header p { font-size: 14px; color: var(--color-text-tertiary); }
.settings-content { min-height: 400px; }
.readiness-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr)) auto;
  gap: 12px;
  align-items: stretch;
  margin-bottom: 18px;
}
.ready-item {
  min-height: 72px;
  display: flex;
  gap: 12px;
  align-items: center;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: #fff;
  padding: 12px 14px;
}
.ready-item > span {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  border: 2px solid currentColor;
  flex: 0 0 auto;
}
.ready-item.ok { color: var(--color-success); }
.ready-item.warn { color: var(--color-warning); }
.ready-item div { display: grid; gap: 3px; min-width: 0; }
.ready-item strong { color: var(--color-text); font-size: 14px; }
.ready-item small {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-secondary);
  font-size: 12px;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.readiness-summary .secondary-btn {
  height: auto;
  min-width: 112px;
}
.settings-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.tts-card, .runtime-card { grid-column: 1 / -1; }
.tts-card .fields-row, .runtime-card .fields-row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 24px; }
.auth-method-field { grid-column: 1 / -1; }
.settings-card {
  background: var(--color-card); border: 1px solid var(--color-border);
  border-radius: var(--radius-sm); padding: 22px; box-shadow: var(--shadow-sm);
}
.card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 20px; }
.card-header h2 { font-size: 18px; color: var(--color-text); }
.card-tag {
  font-size: 12px; color: var(--color-primary); background: var(--color-primary-bg);
  border-radius: 6px; padding: 4px 8px; font-weight: 600;
}
.field { display: block; margin-bottom: 16px; }
.field span { display: block; font-size: 13px; color: var(--color-text-tertiary); margin-bottom: 8px; font-weight: 500; }
.field-help { display: block; margin-top: 7px; color: var(--color-text-tertiary); font-size: 12px; line-height: 1.45; }
.text-input {
  width: 100%; height: 40px; padding: 0 12px; border: 1px solid var(--color-border);
  border-radius: var(--radius-sm); background: var(--color-bg); color: var(--color-text);
  font-size: 14px; outline: none; transition: border-color 0.15s, box-shadow 0.15s;
}
.text-input:focus { border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-bg); background: var(--color-card); }
.model-picker { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; }
.model-select { margin-top: 8px; }
.compact-btn {
  min-width: 112px; height: 40px; padding: 0 12px;
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
}
.protocol-group { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.protocol-btn {
  height: 38px; border: 1px solid var(--color-border); border-radius: var(--radius-sm);
  background: var(--color-bg); color: var(--color-text-secondary);
  font-size: 13px; font-weight: 600; cursor: pointer;
}
.protocol-btn.active { border-color: var(--color-primary); background: var(--color-primary-bg); color: var(--color-primary); }
.settings-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 14px; }
.tts-test-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 4px;
}

.tts-test-row audio {
  width: min(420px, 100%);
  height: 36px;
}
.secondary-btn, .primary-btn {
  height: 40px; padding: 0 22px; border-radius: var(--radius-sm);
  font-size: 14px; font-weight: 600; cursor: pointer; border: none;
}
.secondary-btn { background: var(--color-card); color: var(--color-text-secondary); border: 1px solid var(--color-border); }
.primary-btn { min-width: 112px; background: var(--color-primary); color: #fff; display: inline-flex; align-items: center; justify-content: center; }
.primary-btn:disabled, .secondary-btn:disabled { opacity: 0.55; cursor: not-allowed; }

@media (max-width: 820px) {
  .settings-main { width: calc(100% - 28px); padding: 24px 0 36px; }
  .readiness-summary { grid-template-columns: 1fr; }
  .settings-grid { grid-template-columns: 1fr; }
  .tts-card .fields-row, .runtime-card .fields-row { grid-template-columns: 1fr; }
  .model-picker { grid-template-columns: 1fr; }
  .compact-btn { width: 100%; }
}
</style>
