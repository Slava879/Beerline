import http from './http'

// Кандидаты на назначение/замену инженера (ReassignModal, EngineerReplacementModal).
//
// ВАЖНО ДЛЯ БЭКЕНДЕРА: в текущих моках есть поля вроде nameColor, dot, skillTag.bg,
// border, iconColor и т.п. — это чисто фронтовая логика отображения (какой цвет
// текста/бейджа рисовать), бэкенду их присылать НЕ нужно. От бэкенда нужны только
// "сырые" данные: доступен ли инженер, рекомендован ли он, транспорт, загрузка,
// расстояние/ETA, есть ли нужное оборудование. Раскраску карточки фронт посчитает
// сам на основе available/recommended/isOptimal — это и будет частью завтрашней
// работы по интеграции.

// GET /requests/:requestId/reassign-candidates
// -> [{ id, name, transport, load, deviation, stock, stockOk, isOptimal, reason }]
// используется в ReassignModal
export const getReassignCandidates = async (requestId) => {
    const { data } = await http.get(`/requests/${requestId}/reassign-candidates`)
    return data
}

// GET /requests/:requestId/replacement-candidates
// -> [{ id, name, available, recommended, transport, load, skills: [], hasRequiredEquipment, distanceKm, etaMinutes }]
// используется в EngineerReplacementModal
export const getReplacementCandidates = async (requestId) => {
    const { data } = await http.get(`/requests/${requestId}/replacement-candidates`)
    return data
}
