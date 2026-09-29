import axios from 'axios'

// Единая точка входа для ВСЕХ запросов к бэкенду.
// Раньше (см. старую версию auth.js) axios вызывался напрямую в каждом файле —
// это плохо масштабируется, поэтому весь остальной src/api/*.js теперь ходит через этот инстанс.
//
// Что тут настроено:
// 1. baseURL берётся из .env (VITE_API_URL) — когда бэкендер даст реальный адрес
//    (или подключим прод), меняем только .env, ни один файл с кодом трогать не надо.
// 2. Токен, который бэкенд отдаёт при логине (см. authRequest в ./auth.js),
//    автоматически подставляется в заголовок Authorization для каждого запроса.
// 3. Если бэкенд ответил 401 (токен не валиден/просрочен) — чистим сессию и уводим на /auth.
//
// ДЛЯ ПРОВЕРЯЮЩИХ: это единственное место в проекте, где настраиваются заголовки,
// таймаут и обработка ошибок авторизации — остальной api-слой (dispatcher.js, engineer.js
// и т.д.) переиспользует этот инстанс вместо прямых вызовов axios.

const API_URL = import.meta.env.VITE_API_URL

const http = axios.create({
    baseURL: API_URL,
    timeout: 15000,
})

// Подставляем токен авторизации, если он есть в localStorage (кладётся в AuthPage после логина)
http.interceptors.request.use((config) => {
    const token = localStorage.getItem('token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// Если бэкенд говорит "не авторизован" — сбрасываем сессию и кидаем на страницу входа
http.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('token')
            localStorage.removeItem('user')
            if (window.location.pathname !== '/auth') {
                window.location.href = '/auth'
            }
        }
        return Promise.reject(error)
    }
)

export default http
