import http from './http'
const API_URL = import.meta.env.VITE_API_URL;

// POST /auth — логин.
// Ожидаемый ответ бэкенда (уточнить точный контракт у бэкендера/в свагере):
// { token: string, user: { id, name, role: 'dispatcher' | 'engineer' } }
//
// role — обязательное поле для фронта: по нему решаем, куда вести пользователя
// после входа (диспетчер -> /dispatcher, инженер -> /engineer).
// Сейчас, пока бэкенда нет, роль временно вычисляется на глаз в AuthForm.jsx —
// когда появится реальный ответ, эту заглушку в AuthForm.jsx нужно убрать
// (там же стоит комментарий с пометкой, что удалить).
export const authRequest = async (data) => {
    const response = await http.post(`${API_URL}/auth/login`, data)
    return response.data
}