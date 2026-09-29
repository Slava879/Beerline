import http from './http'

// Запросы для страницы инженера (src/pages/EngineerPage/EngineerPage.jsx).

// GET /engineer/requests -> { openRequest: {...}, queuedRequests: [...] }
// openRequest — заявка, в работе прямо сейчас (всегда развёрнута и на виду).
// queuedRequests — остальные заявки на день (по кнопке "Показать все заявки").
export const getEngineerRequests = async () => {
    const { data } = await http.get('/engineer/requests')
    return data
}

// POST /requests/:requestId/stage — сменить этап работы по заявке.
// stage: 'take' | 'start' | 'stop' — см. WorkStagesFooter.jsx, массив STAGES.
// ВАЖНО: сейчас WorkStagesFooter хранит текущий этап только у себя внутри (useState)
// и никуда не сообщает о смене — чтобы дёрнуть этот запрос, туда нужно будет
// добавить проп-коллбэк (например onStageChange), см. пометку в самом WorkStagesFooter.jsx.
export const updateRequestStage = async (requestId, stage) => {
    const response = await http.post(`/requests/${requestId}/stage`, { stage })
    return response.data
}

// POST /requests/:requestId/cancel-by-client — кнопка "Клиент отменил заявку" (WorkStagesFooter)
export const cancelRequestByClient = async (requestId) => {
    const response = await http.post(`/requests/${requestId}/cancel-by-client`)
    return response.data
}
