// src/api/client.js
const API_URL = import.meta.env.VITE_API_URL ?? ''

const getAccess  = () => localStorage.getItem('access_token')
const getRefresh = () => localStorage.getItem('refresh_token')

const setTokens = ({ access_token, refresh_token }) => {
    if (access_token)  localStorage.setItem('access_token', access_token)
    if (refresh_token) localStorage.setItem('refresh_token', refresh_token)
}

const clearTokens = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
}

let refreshing = null

const refreshTokens = async () => {
    if (refreshing) return refreshing
    refreshing = (async () => {
        const rt = getRefresh()
        if (!rt) throw new Error('NO_REFRESH')

        const res = await fetch(`${API_URL}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: rt }),
        })
        if (!res.ok) {
            clearTokens()
            window.location.href = '/auth/login'
            throw new Error('REFRESH_FAILED')
        }
        const data = await res.json()
        setTokens(data)
        return data.access_token
    })().finally(() => { refreshing = null })
    return refreshing
}

export const request = async (path, { method = 'GET', body, headers, isForm } = {}) => {
    const buildHeaders = (token) => {
        const h = { ...(headers || {}) }
        if (token) h.Authorization = `Bearer ${token}`
        if (!isForm && body !== undefined) h['Content-Type'] = 'application/json'
        return h
    }

    const doFetch = (token) => fetch(`${API_URL}${path}`, {
        method,
        headers: buildHeaders(token),
        body: isForm ? body : (body !== undefined ? JSON.stringify(body) : undefined),
    })

    let res = await doFetch(getAccess())

    if (res.status === 401) {
        try {
            const newToken = await refreshTokens()
            res = await doFetch(newToken)
        } catch {
            // refresh не удался — пробрасываем исходную 401
        }
    }

    if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
            const j = await res.json()
            msg = j.detail || j.message || msg
        } catch {}
        throw new Error(msg)
    }
    if (res.status === 204) return null
    return res.json().catch(() => null)
}

export const get      = (p, opts)       => request(p, { ...opts, method: 'GET' })
export const post     = (p, body, opts) => request(p, { ...opts, method: 'POST', body })
export const patch    = (p, body, opts) => request(p, { ...opts, method: 'PATCH', body })
export const del      = (p, body, opts) => request(p, { ...opts, method: 'DELETE', body })
export const postForm = (p, formData, opts) =>
    request(p, { ...opts, method: 'POST', body: formData, isForm: true })

export { setTokens, clearTokens, getAccess, getRefresh }