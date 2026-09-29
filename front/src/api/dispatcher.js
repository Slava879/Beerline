// src/api/dispatcher.js
import { get, post, patch, del } from './client'

const D = '/dispatcher'

// ---------- Dashboard ----------
export const getDispatcherDashboard = (districtId, visitDate) => {
    const params = new URLSearchParams({ district_id: districtId })
    if (visitDate) params.set('visit_date', visitDate)
    return get(`${D}/dashboard?${params.toString()}`)
}

export const getReplanningEvents = (districtId) =>
    get(`${D}/replanning-events?district_id=${encodeURIComponent(districtId)}`)

// ---------- Заявки ----------
export const assignRequest       = (rid, eid) => post(`${D}/requests/${rid}/assign/${eid}`)
export const returnRequestToPool = (rid)      => post(`${D}/requests/${rid}/return`)
export const autoAssignRequest   = (rid)      => post(`${D}/requests/${rid}/auto-assign`)
export const confirmRequest      = (rid)      => post(`${D}/requests/${rid}/confirm`)
export const updateRequestStatus = (rid, status) => post(`${D}/requests/${rid}/status`, { status })
export const updateCoords        = (rid, lat, lon) => patch(`${D}/requests/${rid}/coords`, { lat, lon })
export const restoreRequest      = (rid)      => post(`${D}/requests/${rid}/restore`)
export const createUrgentRequest = (data)     => post(`${D}/requests/urgent`, data)

// resetAllRequests теперь принимает дату
export const resetAllRequests = (districtId, mode = 'planned', visitDate = null) => {
    const params = new URLSearchParams({ district_id: districtId, mode })
    if (visitDate) params.set('visit_date', visitDate)
    return post(`${D}/requests/reset?${params.toString()}`)
}

export const getSuitableEngineers = (rid, districtId, visitDate) => {
    const params = new URLSearchParams({ district_id: districtId })
    if (visitDate) params.set('visit_date', visitDate)
    return get(`${D}/requests/${rid}/suitable-engineers?${params.toString()}`)
}

// ---------- Инженеры ----------
export const createEngineer     = (data)        => post(`${D}/engineers`, data)
export const getEngineerDetails = (eid)         => get(`${D}/engineers/${eid}`)
export const updateEngineer     = (eid, d)      => patch(`${D}/engineers/${eid}`, d)
export const endShift           = (eid, reason) => post(`${D}/engineers/${eid}/shift/end`, { reason })
export const startShift         = (eid)         => post(`${D}/engineers/${eid}/shift/start`)
export const printTmlAct        = (eid)         => post(`${D}/engineers/${eid}/tml/print`)

// ---------- Оборудование ----------
export const listEquipment     = ()                => get(`${D}/equipment`)
export const createEquipment   = (data)            => post(`${D}/equipment`, data)
export const patchEquipment    = (eqId, data)      => patch(`${D}/equipment/${eqId}`, data)
export const deleteEquipment   = (eqId)            => del(`${D}/equipment/${eqId}`)
export const issueEquipment    = (eid, eqId, qty)  => post(`${D}/engineers/${eid}/equipment`, { equipment_id: eqId, quantity: qty })
export const returnEquipment   = (eid, eqId, qty)  => post(`${D}/engineers/${eid}/equipment/${eqId}/return`, { quantity: qty })
export const revokeEquipment   = (eid, eqId)       => del(`${D}/engineers/${eid}/equipment/${eqId}`)
export const clearEngineerEquip = (eid)            => del(`${D}/engineers/${eid}/equipment`)

// ---------- Распределение и карты ----------
export const distributeOrders = (districtId, visitDate, regeocode = false) => {
    const params = new URLSearchParams({ district_id: districtId })
    if (visitDate) params.set('visit_date', visitDate)
    if (regeocode) params.set('regeocode', 'true')
    return post(`${D}/distribute?${params.toString()}`)
}

export const getEngineerMap = (eid, districtId) =>
    get(`${D}/engineers/${eid}/map?district_id=${encodeURIComponent(districtId)}`)

export const getLatestMap = (districtId) =>
    get(`${D}/maps/latest?district_id=${encodeURIComponent(districtId)}`)

export const rebuildMaps = (districtId, visitDate) => {
    const params = new URLSearchParams({ district_id: districtId })
    if (visitDate) params.set('visit_date', visitDate)
    return post(`${D}/maps/rebuild?${params.toString()}`)
}