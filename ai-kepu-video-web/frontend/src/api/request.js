/**
 * Axios 封装
 * 统一配置 baseURL、拦截器、错误处理
 */

import axios from 'axios'
import { ElMessage } from 'element-plus'

// 从环境变量读取 API 地址
const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:2002'

// 创建 axios 实例
const request = axios.create({
  baseURL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
request.interceptors.request.use(
  config => {
    // 可以在这里添加 token
    // const token = localStorage.getItem('token')
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }

    console.log('[API Request]', config.method.toUpperCase(), config.url)
    return config
  },
  error => {
    console.error('[API Request Error]', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  response => {
    console.log('[API Response]', response.config.url, response.status)
    return response.data
  },
  error => {
    console.error('[API Response Error]', error)

    // 网络错误
    if (!error.response) {
      ElMessage.error('网络异常，请检查连接')
      return Promise.reject(new Error('网络异常'))
    }

    // HTTP 错误
    const { status, data } = error.response

    switch (status) {
      case 404:
        ElMessage.error(data?.detail || '资源不存在')
        break
      case 429:
        ElMessage.error('服务繁忙，请稍后重试')
        break
      case 500:
        ElMessage.error('服务器错误')
        break
      default:
        ElMessage.error(data?.detail || '请求失败')
    }

    return Promise.reject(error)
  }
)

export default request
