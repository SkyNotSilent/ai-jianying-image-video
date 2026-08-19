/**
 * Axios 封装
 * 统一配置 baseURL、拦截器、错误处理
 */

import axios from 'axios'
import {
  safeApiLogArgs,
  safeApiRequestLogArgs,
  toSafeApiError,
} from '../lib/apiErrorSafety'
import { toast } from '../lib/toast'

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

    console.log(...safeApiRequestLogArgs('[API Request]', config))
    return config
  },
  error => {
    const safeError = toSafeApiError(error)
    if (safeError.kind === 'cancelled') return Promise.reject(safeError)
    console.error(...safeApiLogArgs('[API Request Error]', safeError))
    return Promise.reject(safeError)
  }
)

// 响应拦截器
request.interceptors.response.use(
  response => {
    console.log(...safeApiRequestLogArgs('[API Response]', response.config, response.status))
    return response.data
  },
  error => {
    const suppressToast = Boolean(error?.config?.suppressToast)
    const safeError = toSafeApiError(error)
    if (safeError.kind === 'cancelled') return Promise.reject(safeError)
    console.error(...safeApiLogArgs('[API Response Error]', safeError))

    if (suppressToast) return Promise.reject(safeError)

    // 网络错误
    if (!safeError.response) {
      toast.error('网络异常，请检查连接')
      return Promise.reject(safeError)
    }

    // HTTP 错误
    const { status, data } = safeError.response

    switch (status) {
      case 404:
        toast.error(data?.detail || '资源不存在')
        break
      case 429:
        toast.error('服务繁忙，请稍后重试')
        break
      case 500:
        toast.error('服务器错误')
        break
      default:
        toast.error(data?.detail || '请求失败')
    }

    return Promise.reject(safeError)
  }
)

export default request
