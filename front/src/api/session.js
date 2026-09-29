let currentUser = null

export const setSession = (user) => {
    currentUser = user
    if (user) {
        localStorage.setItem('user', JSON.stringify(user))
    } else {
        localStorage.removeItem('user')
    }
}

export const getSession = () => {
    if (currentUser) return { user: currentUser }
    const raw = localStorage.getItem('user')
    if (!raw) return null
    try {
        currentUser = JSON.parse(raw)
        return { user: currentUser }
    } catch {
        return null
    }
}

export const clearSession = () => {
    currentUser = null
    localStorage.removeItem('user')
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
}