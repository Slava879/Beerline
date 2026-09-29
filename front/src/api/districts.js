// src/api/districts.js
import { get, post, patch, del, postForm } from './client'

// ─── Уведомление страницы «Диспетчер» об изменении состава заявок ───
function notifyOrdersChanged() {
    try {
        // Сработает во всех других вкладках того же origin (событие 'storage')
        localStorage.setItem('orders_changed', String(Date.now()))
    } catch (e) { /* ignore */ }
    try {
        // Сработает в текущей вкладке (SPA), если на ней смонтирован DispatcherPage
        window.dispatchEvent(new Event('ordersChanged'))
    } catch (e) { /* ignore */ }
}

export const getDistricts  = ()         => get('/districts')
export const getDistrict   = (id)       => get(`/districts/${id}`)
export const patchDistrict = (id, data) => patch(`/districts/${id}`, data)

export const uploadCsv = async (file) => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await postForm('/districts/upload-csv', fd)

    // ← вот это: говорим диспетчеру «состав заявок изменился»
    notifyOrdersChanged()

    return res
}

export const deleteDistrictData = async (districtId, period) => {
    const res = await del(`/districts/${districtId}/data`, { period })

    notifyOrdersChanged()

    return res
}