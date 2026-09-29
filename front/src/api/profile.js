import http from './http'

// GET /profile -> { name, post, status, plan, route, trunk }
// Сейчас в ProfileModal.jsx имя и роль берутся из локальной сессии (getSession(),
// которая кладётся при логине в AuthForm.jsx), а план/маршрут/статус — из мока
// profileData. Когда появится этот эндпоинт, всё можно будет получать одним
// запросом вместо смеси localStorage + мока.
export const getProfile = async () => {
    const { data } = await http.get('/profile')
    return data
}
