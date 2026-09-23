import axios from 'axios'
import { useEffect, useReducer, useState } from 'react'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api', timeout: 60000 })
api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('reviewguard_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
export function errorMessage(error) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join('. ')
  return error?.code === 'ECONNABORTED' ? 'The request took too long. Please try again.' : 'Could not reach the server. Check that the backend is running, then try again.'
}
export function useResource(url) {
  const [version, refresh] = useReducer((value) => value + 1, 0)
  const [state, setState] = useState({ data: null, loading: true, error: '' })
  useEffect(() => {
    const controller = new AbortController()
    api.get(url, { signal: controller.signal }).then(({ data }) => setState({ data, loading: false, error: '' })).catch((error) => {
      if (!axios.isCancel(error)) setState((previous) => ({ ...previous, loading: false, error: errorMessage(error) }))
    })
    return () => controller.abort()
  }, [url, version])
  return { ...state, refresh }
}
