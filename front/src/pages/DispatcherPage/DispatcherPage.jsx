import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import PageHeader from '../../components/PageHeader/PageHeader'
import ReassignModal from '../../components/ReassignModal/ReassignModal'
import ChoiceDistrictModal from '../../components/ChoiceDistrictModal/ChoiceDistrictModal'
import EngineerMenuModal from '../../components/EngineerMenuModal/EngineerMenuModal'
import EngineerFormModal from '../../components/EngineerFormModal/EngineerFormModal'
import EquipmentFormModal from '../../components/EquipmentFormModal/EquipmentFormModal'
import EquipmentListModal from '../../components/EquipmentListModal/EquipmentListModal'
import UrgentRequestModal from '../../components/UrgentRequestModal/UrgentRequestModal'
import EditCoordsModal from '../../components/EditCoordsModal/EditCoordsModal'
import ReplanningEventCard from './ReplanningEventCard'
import UnallocatedCard from './UnallocatedCard'
import DistributedCard from './DistributedCard'
import IncomingRequestToast from '../../components/IncomingRequestToast/IncomingRequestToast'
import Toast from '../../components/Toast/Toast'
import {
    getDispatcherDashboard, getReplanningEvents,
    assignRequest, returnRequestToPool, autoAssignRequest,
    confirmRequest, createUrgentRequest, createEngineer,
    createEquipment, updateRequestStatus, updateCoords,
    distributeOrders, getEngineerMap, getLatestMap, resetAllRequests,
    rebuildMaps, restoreRequest,
} from '../../api/dispatcher'
import { getAccess } from '../../api/client'
import './DispatcherPage.css'

const WS_URL = (import.meta.env.VITE_WS_URL ?? '') + '/ws/dispatcher'
const API_BASE = import.meta.env.VITE_API_URL ?? ''

const STATUS_LABEL_RU = {
    taken:       'Выехал на заявку',
    in_progress: 'Начал работу',
    done:        'Работу завершил',
    cancelled:   'Заявка отменена',
    new:         'Новая',
}

const todayISO = () => {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const SORT_BY_TYPE = 'type'
const SORT_BY_ENGINEER = 'engineer'

const DispatcherPage = () => {
    const [district, setDistrict] = useState(null)
    const [visitDate, setVisitDate] = useState(todayISO())

    const [engineers,         setEngineers]         = useState({})
    const [plannedRequests,   setPlannedRequests]   = useState({})
    const [unallocated,       setUnallocated]       = useState({})
    const [cancelledRequests, setCancelledRequests] = useState({})
    const [replanningEvents,  setReplanningEvents]  = useState([])

    const [loading,      setLoading]      = useState(false)
    const [loadError,    setLoadError]    = useState(null)
    const [distributing, setDistributing] = useState(false)
    const [resetting,    setResetting]    = useState(false)

    const [mapPanelUrl,   setMapPanelUrl]   = useState(null)
    const [mapPanelTitle, setMapPanelTitle] = useState('')
    const [mapRefreshKey, setMapRefreshKey] = useState(0)
    const [mapRefreshing, setMapRefreshing] = useState(false)
    const [mapUrls,       setMapUrls]       = useState({})

    const [activeUnallocatedId, setActiveUnallocatedId] = useState(null)
    const [activeRequestId,     setActiveRequestId]     = useState(null)
    const [statusBusy,          setStatusBusy]          = useState(false)

    const [reassignRequest, setReassignRequest] = useState(null)
    const [isDistrictOpen,  setIsDistrictOpen]  = useState(false)
    const [menuEngineerId,  setMenuEngineerId]  = useState(null)
    const [isUrgentOpen,    setIsUrgentOpen]    = useState(false)
    const [tab,             setTab]             = useState('unallocated')
    const [isCreateOpen,    setIsCreateOpen]    = useState(false)
    const [isEqListOpen,    setIsEqListOpen]    = useState(false)
    const [isEqCreateOpen,  setIsEqCreateOpen]  = useState(false)
    const [incoming,        setIncoming]        = useState([])

    const [sortBy,        setSortBy]        = useState('none')
    const [coordsEditReq, setCoordsEditReq] = useState(null)

    // ─── Тосты ─────────────────────────────────────────────
    const [toasts, setToasts] = useState([])
    const showToast = useCallback((text, type = 'info', duration = 3500) => {
        const id = `${Date.now()}-${Math.random()}`
        setToasts((prev) => [...prev, { id, text, type, duration }])
    }, [])
    const dismissToast = useCallback((id) => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
    }, [])

    const wsRef = useRef(null)
    const activeCardRef = useRef(null)

    const loadDashboard = useCallback(async (districtId, dateStr) => {
        setLoading(true); setLoadError(null)
        try {
            const [dash, events] = await Promise.all([
                getDispatcherDashboard(districtId, dateStr),
                getReplanningEvents(districtId),
            ])
            setEngineers(dash.engineers ?? {})
            setPlannedRequests(dash.planned_requests ?? {})
            setUnallocated(dash.unallocated_requests ?? {})
            setCancelledRequests(dash.cancelled_requests ?? {})
            setReplanningEvents(events ?? [])
        } catch (e) {
            setLoadError(e?.message || 'Не удалось загрузить данные')
        } finally { setLoading(false) }
    }, [])

    const refresh = useCallback(() => {
        if (district?.id) loadDashboard(district.id, visitDate)
    }, [district?.id, visitDate, loadDashboard])

    useEffect(() => {
        if (!district?.id) return
        loadDashboard(district.id, visitDate)
    }, [district?.id, visitDate, loadDashboard])

    // Автообновление раз в 60 секунд
    useEffect(() => {
        if (!district?.id) return
        const t = setInterval(() => loadDashboard(district.id, visitDate), 60_000)
        return () => clearInterval(t)
    }, [district?.id, visitDate, loadDashboard])

    // Реакция на возврат на вкладку
    useEffect(() => {
        if (!district?.id) return
        const onVisible = () => {
            if (document.visibilityState === 'visible') refresh()
        }
        const onFocus = () => refresh()
        window.addEventListener('visibilitychange', onVisible)
        window.addEventListener('focus', onFocus)
        return () => {
            window.removeEventListener('visibilitychange', onVisible)
            window.removeEventListener('focus', onFocus)
        }
    }, [district?.id, refresh])

    // Кросс-вкладочное событие
    useEffect(() => {
        if (!district?.id) return
        const onStorage = (e) => {
            if (e.key === 'orders_changed') {
                console.log('[STORAGE] orders_changed:', e.newValue)
                refresh()
            }
        }
        window.addEventListener('storage', onStorage)
        return () => window.removeEventListener('storage', onStorage)
    }, [district?.id, refresh])

    // Локальное событие
    useEffect(() => {
        if (!district?.id) return
        const onLocal = () => {
            console.log('[EVENT] ordersChanged')
            refresh()
        }
        window.addEventListener('ordersChanged', onLocal)
        return () => window.removeEventListener('ordersChanged', onLocal)
    }, [district?.id, refresh])

    useEffect(() => {
        if (!activeRequestId) return
        const t = setTimeout(() => {
            activeCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
        }, 50)
        return () => clearTimeout(t)
    }, [activeRequestId])

    // ---------- WebSocket ----------
    useEffect(() => {
        if (!district?.id) return
        let ws; let reconnectTimer
        const connect = () => {
            const token = getAccess()
            ws = new WebSocket(`${WS_URL}?district_id=${encodeURIComponent(district.id)}&token=${token}`)
            wsRef.current = ws
            ws.onmessage = (ev) => {
                try {
                    const msg = JSON.parse(ev.data)
                    if (msg.type === 'incoming_request') {
                        setIncoming((prev) => [...prev, msg.payload])
                    } else if (msg.type === 'request_status_changed') {
                        setPlannedRequests((prev) => {
                            const cur = prev[msg.payload.id]
                            if (!cur) return prev
                            return { ...prev, [msg.payload.id]: { ...cur, ...msg.payload } }
                        })
                    } else if (msg.type === 'engineer_updated') {
                        setEngineers((prev) => ({ ...prev, [msg.payload.id]: msg.payload }))
                    }
                } catch (err) { console.error('WS parse', err) }
            }
            ws.onclose = () => { reconnectTimer = setTimeout(connect, 3000) }
        }
        connect()
        return () => {
            clearTimeout(reconnectTimer)
            wsRef.current?.close()
            wsRef.current = null
        }
    }, [district?.id])

    const handleSelectDistrict = (d) => {
        setIsDistrictOpen(false)
        if (d.id === district?.id) return
        setEngineers({}); setPlannedRequests({}); setUnallocated({})
        setCancelledRequests({})
        setReplanningEvents([]); setIncoming([])
        setReassignRequest(null); setMenuEngineerId(null)
        setActiveRequestId(null); setActiveUnallocatedId(null)
        setMapUrls({}); setMapPanelUrl(null); setMapPanelTitle('')
        setDistrict(d)
    }

    const handleAcceptIncoming = async (id) => {
        const toast = incoming.find((t) => t.id === id)
        setIncoming((prev) => prev.filter((t) => t.id !== id))
        if (!toast) return
        try { await confirmRequest(id); await refresh() } catch (e) { console.error(e) }
    }
    const handleDismissIncoming = (id) =>
        setIncoming((prev) => prev.filter((t) => t.id !== id))

    const openReassign = (event) => setReassignRequest({
        id: event.requestId,
        address: event.description?.replace('Адрес: ', '').split(' | ')[0] || '',
        service: 'Подключение XGS-PON',
        equipmentNote: 'Роутер Wi-Fi 6 Pro (1 шт)',
        reason: event.title,
        sla: '12:00',
    })

    // ---------- Панель карты ----------
    const openMapPanel = (url, title) => {
        setMapPanelUrl(url ? API_BASE + url : null)
        setMapPanelTitle(title || 'Карта')
        setMapRefreshKey((k) => k + 1)
    }
    const closeMapPanel = () => {
        setMapPanelUrl(null); setMapPanelTitle('')
    }

    const handleShowAllMap = async () => {
        if (!district?.id) return
        try {
            const res = await getLatestMap(district.id)
            if (res?.map_url) openMapPanel(res.map_url, 'Общая карта всех мастеров')
            else showToast('Общая карта ещё не построена. Нажмите «Распределить заявки».', 'warning')
        } catch (e) { console.error(e) }
    }

    const refreshMapsAfterChange = useCallback(async () => {
        if (!district?.id) return
        try {
            const maps = await rebuildMaps(district.id, visitDate)
            if (!maps?.ok) return

            if (maps.per_engineer) {
                setMapUrls((prev) => ({ ...prev, ...maps.per_engineer }))
            }

            if (mapPanelUrl) {
                const current = mapPanelUrl

                if (/\/all_\d+\.html(\?.*)?$/.test(current)) {
                    if (maps.map_url) setMapPanelUrl(API_BASE + maps.map_url)
                } else {
                    const m = current.match(/\/engineer_([0-9a-fA-F-]{36})_\d+\.html(\?.*)?$/)
                    if (m) {
                        const eid = m[1]
                        const fresh = maps.per_engineer?.[eid]
                        if (fresh) {
                            setMapPanelUrl(API_BASE + fresh)
                        } else if (maps.map_url) {
                            setMapPanelUrl(API_BASE + maps.map_url)
                            setMapPanelTitle('Общая карта всех мастеров')
                        } else {
                            closeMapPanel()
                        }
                    }
                }
            }

            setMapRefreshKey((k) => k + 1)
        } catch (e) {
            console.error('[MAPS] rebuild failed', e)
        }
    }, [district?.id, visitDate, mapPanelUrl])

    const handleManualRefreshMap = async () => {
        if (!district?.id || mapRefreshing) return
        setMapRefreshing(true)
        try {
            await refreshMapsAfterChange()
            showToast('Карта обновлена', 'success')
        } finally {
            setMapRefreshing(false)
        }
    }

    const refreshEngineerMap = async (eid, ev) => {
        ev?.stopPropagation?.()
        if (!district?.id || mapRefreshing) return
        setMapRefreshing(true)
        try {
            const maps = await rebuildMaps(district.id, visitDate)
            if (!maps?.ok) {
                showToast('Не удалось обновить карты', 'error')
                return
            }
            if (maps.per_engineer) {
                setMapUrls((prev) => ({ ...prev, ...maps.per_engineer }))
            }
            const fresh = maps.per_engineer?.[eid]
            const eng = engineers[eid]
            if (fresh) {
                openMapPanel(fresh, `Карта мастера ${eng?.name ?? ''}`)
            } else {
                showToast('У мастера нет заявок на эту дату.', 'warning')
            }
        } catch (e) {
            console.error('[MAPS] refreshEngineerMap failed', e)
            showToast('Не удалось обновить карту: ' + (e?.message || ''), 'error')
        } finally {
            setMapRefreshing(false)
        }
    }

    // ---------- Распределение ----------
    const handleDistribute = async () => {
        if (!district?.id || distributing) return
        const regeocode = window.confirm(
            'Перекодировать все адреса?\n\n' +
            'ОК — геокодировать все адреса заново.\n' +
            'Отмена — геокодировать только те, у которых ещё нет координат.'
        )
        setDistributing(true)
        try {
            const res = await distributeOrders(district.id, visitDate, regeocode)
            if (res?.ok) {
                setMapUrls(res.per_engineer ?? {})
                await refresh()
                const lines = [`Распределено: ${res.assigned} из ${res.total}`]
                if (res.unassigned?.length) {
                    lines.push(`Не назначено: ${res.unassigned.length}`)
                    for (const u of res.unassigned.slice(0, 5)) lines.push(`• #${u.id} — ${u.reason}`)
                    if (res.unassigned.length > 5) lines.push(`… и ещё ${res.unassigned.length - 5}`)
                }
                showToast(lines.join(' · '), 'success', 5000)
                if (res.map_url) openMapPanel(res.map_url, 'Общая карта всех мастеров')
            } else {
                showToast(res?.error || 'Не удалось распределить заявки', 'error')
            }
        } catch (e) {
            showToast('Ошибка: ' + e.message, 'error')
        } finally {
            setDistributing(false)
        }
    }

    const handleResetAllRequests = async () => {
        if (!district?.id || resetting) return
        const all = window.confirm(
            'Сбросить заявки и вернуть оборудование?\n\n' +
            'ОК — сбросить ВСЕ заявки на эту дату (включая нераспределённые).\n' +
            'Отмена — выбрать другой вариант.'
        )
        let mode
        if (all) mode = 'all'
        else {
            const onlyPlanned = window.confirm('Сбросить только запланированные (не начатые) заявки с мастером?')
            if (!onlyPlanned) return
            mode = 'planned'
        }

        setResetting(true)
        try {
            await resetAllRequests(district.id, mode, visitDate)
            await refresh()
            setActiveRequestId(null)
            setMapUrls({})
            await refreshMapsAfterChange()
            showToast('Заявки сброшены', 'success')
        } catch (e) {
            showToast('Ошибка: ' + e.message, 'error')
        } finally {
            setResetting(false)
        }
    }

    // ---------- Действия ----------
    const handleAssign = async (rid, eid) => {
        try {
            const eng = engineers[eid]
            await assignRequest(rid, eid)
            await refresh()
            setReassignRequest(null)
            setActiveUnallocatedId(null)
            setActiveRequestId(null)
            await refreshMapsAfterChange()
            showToast(`Заявка назначена мастеру ${eng?.name ?? ''}`, 'success')
        } catch (e) {
            console.error(e)
            showToast('Не удалось назначить мастера: ' + (e?.message || ''), 'error')
        }
    }

    const handleReturnToPool = async (rid) => {
        try {
            await returnRequestToPool(rid); await refresh()
            setReassignRequest(null); setActiveRequestId(null)
            await refreshMapsAfterChange()
            showToast('Заявка вернулась в нераспределённые', 'info')
        } catch (e) {
            console.error(e)
            showToast('Не удалось вернуть заявку', 'error')
        }
    }

    const handleAutoAssign = async (rid) => {
        try {
            await autoAssignRequest(rid)
            await refresh()
            setReassignRequest(null)
            await refreshMapsAfterChange()
            showToast('Мастер назначен автоматически', 'success')
        } catch (e) {
            console.error(e)
            showToast('Не удалось назначить автоматически', 'error')
        }
    }

    const handleStatusChange = async (rid, status) => {
        if (!rid || !status) return
        setStatusBusy(true)
        try {
            const updated = await updateRequestStatus(rid, status)
            if (updated && updated.id) {
                setPlannedRequests((prev) => ({ ...prev, [updated.id]: { ...(prev[updated.id] || {}), ...updated } }))
            }
            await refresh()

            const s = String(status).toLowerCase()
            const label = STATUS_LABEL_RU[s] || s
            const extId = updated?.external_id ?? updated?.id ?? rid
            if (s === 'cancelled') {
                showToast(`Заявка #${extId} — отменена клиентом`, 'warning')
            } else {
                showToast(`Заявка #${extId} — ${label}`, 'success')
            }

            if (s === 'cancelled' || s === 'done') {
                setActiveRequestId(null)
            }
        } catch (e) {
            console.error(e)
            showToast('Не удалось обновить статус: ' + (e?.message || 'ошибка'), 'error')
        } finally {
            setStatusBusy(false)
        }
    }

    const handleCancelRequest = (rid) => handleStatusChange(rid, 'cancelled')

    const handleSaveCoords = async (rid, lat, lon) => {
        try {
            await updateCoords(rid, lat, lon)
            await refresh()
            showToast('Координаты сохранены', 'success')
        } catch (e) {
            showToast('Не удалось сохранить координаты: ' + (e?.message || ''), 'error')
            throw e
        }
    }

    const handleSelectUnallocated = (id) => {
        setActiveUnallocatedId((cur) => (cur === id ? null : id))
        setActiveRequestId(null)
    }
    const handleSelectDistributed = (id) => {
        setActiveRequestId((cur) => (cur === id ? null : id))
        setActiveUnallocatedId(null)
    }

    const handleAssignMasterUnallocated = (request) => setReassignRequest(request)

    const handleClientCancelUnallocated = async (id) => {
        try {
            await updateRequestStatus(id, 'cancelled')
            await refresh()
            setActiveUnallocatedId(null)
            showToast('Заявка отменена клиентом', 'warning')
        } catch (e) {
            console.error(e)
            showToast('Не удалось отменить заявку', 'error')
        }
    }

    const handleRestoreCancelled = async (request) => {
        try {
            await restoreRequest(request.id)
            await refresh()
            showToast(`Заявка #${request.external_id ?? request.id} возвращена в нераспределённые`, 'success')
        } catch (e) {
            console.error(e)
            showToast('Не удалось вернуть заявку: ' + (e?.message || ''), 'error')
        }
    }

    const openEngineerMap = async (eid, ev) => {
        ev?.stopPropagation?.()
        try {
            const eng = engineers[eid]
            if (mapUrls[eid]) {
                openMapPanel(mapUrls[eid], `Карта мастера ${eng?.name ?? ''}`)
                return
            }
            const res = await getEngineerMap(eid, district.id)
            if (res?.map_url) {
                setMapUrls((prev) => ({ ...prev, [eid]: res.map_url }))
                openMapPanel(res.map_url, `Карта мастера ${eng?.name ?? ''}`)
            } else {
                showToast('Сначала распределите заявки.', 'warning')
            }
        } catch (err) { console.error(err) }
    }

    // ─── Списки и сортировка ─────────────────────────────
    const engineersList   = useMemo(() => Object.values(engineers),         [engineers])
    const unallocatedList = useMemo(() => Object.values(unallocated),       [unallocated])
    const plannedListRaw  = useMemo(() => Object.values(plannedRequests),   [plannedRequests])
    const cancelledList   = useMemo(() => Object.values(cancelledRequests), [cancelledRequests])

    const sortedUnallocated = useMemo(() => {
        const arr = [...unallocatedList]
        if (sortBy === SORT_BY_TYPE) {
            arr.sort((a, b) => (a.request_type || '').localeCompare(b.request_type || ''))
        }
        return arr
    }, [unallocatedList, sortBy])

    const sortedCancelled = useMemo(() => {
        const arr = [...cancelledList]
        if (sortBy === SORT_BY_TYPE) {
            arr.sort((a, b) => (a.request_type || '').localeCompare(b.request_type || ''))
        }
        return arr
    }, [cancelledList, sortBy])

    const sortedPlanned = useMemo(() => {
        const arr = [...plannedListRaw]
        if (sortBy === SORT_BY_TYPE) {
            arr.sort((a, b) => (a.request_type || '').localeCompare(b.request_type || ''))
        } else if (sortBy === SORT_BY_ENGINEER) {
            arr.sort((a, b) => {
                const an = engineers[a.engineer_id]?.name || ''
                const bn = engineers[b.engineer_id]?.name || ''
                return an.localeCompare(bn)
            })
        }
        return arr
    }, [plannedListRaw, sortBy, engineers])

    const seqByRequest = useMemo(() => {
        const map = {}
        const byEng = {}
        for (const r of plannedListRaw) {
            if (!r.engineer_id) continue
            byEng[r.engineer_id] = byEng[r.engineer_id] || []
            byEng[r.engineer_id].push(r)
        }
        for (const eid of Object.keys(byEng)) {
            const list = byEng[eid]
            list.sort((a, b) => {
                const ta = a.planned_times?.taken || a.stage_times?.taken || '99:99'
                const tb = b.planned_times?.taken || b.stage_times?.taken || '99:99'
                return ta.localeCompare(tb)
            })
            list.forEach((r, i) => { map[r.id] = i + 1 })
        }
        return map
    }, [plannedListRaw])

    const noDistrict = !district?.id

    const onlineCount = engineersList.filter((e) => e.online).length
    const totalCount  = engineersList.length
    const busyCount   = engineersList.filter((e) => e.online && e.requests > 0).length

    const iframeSrc = mapPanelUrl
        ? `${mapPanelUrl}${mapPanelUrl.includes('?') ? '&' : '?'}_t=${mapRefreshKey}`
        : null

    return (
        <main className="main dispatcher">
            <div className={`dispatcher__layout ${mapPanelUrl ? 'dispatcher__layout--with-map' : ''}`}>

                <div className="dispatcher__content">
                    <section className="section menu__section">
                        <div className="menu__container">

                            <div className="menu__header-wrap">
                                <PageHeader />
                                <div className="menu__date-bar">
                                    <div className="menu__date-bar-label">Дата заявок:</div>
                                    <label className="menu__date-picker">
                                        <span className="menu__date-icon" aria-hidden="true">📅</span>
                                        <input type="date" value={visitDate}
                                               onChange={(e) => setVisitDate(e.target.value)}
                                               aria-label="Выбор даты" />
                                    </label>
                                    {visitDate == todayISO() && (
                                        <button type="button" className="menu__date-today"
                                                onClick={() => setVisitDate(todayISO())}>Сегодня</button>
                                    )}
                                </div>
                            </div>

                            <main className="menu__main">
                                <div className="menu__container">

                                    <div className="menu__buttons">
                                        <button
                                            className={`menu__button-opt${noDistrict || distributing ? ' menu__button--disabled' : ''}`}
                                            disabled={noDistrict || distributing}
                                            onClick={handleDistribute}>
                                            {distributing ? 'Распределение…' : 'Распределить заявки'}
                                        </button>
                                        <button className="menu__button-plan" onClick={() => setIsDistrictOpen(true)}>
                                            {district?.name ?? 'Выбрать участок'}
                                        </button>
                                        <button
                                            className={`menu__button-request${noDistrict ? ' menu__button--disabled' : ''}`}
                                            disabled={noDistrict}
                                            onClick={() => setIsUrgentOpen(true)}>
                                            Добавить заявку
                                        </button>
                                        <button className="menu__button-plan" onClick={handleShowAllMap} disabled={noDistrict}>
                                            Общая карта
                                        </button>
                                    </div>

                                    <div className="menu__masters-info">
                                        <div className="menu__masters-online">
                                            <p className="menu__masters-online-title">Мастера на работе</p>
                                            <p className="menu__master-online-description">
                                                {onlineCount} <span className="menu__master-online-total">/ {totalCount}</span>
                                            </p>
                                        </div>
                                        <div className="menu__masters-busy">
                                            <p className="menu__masters-online-title">Занято заявками</p>
                                            <p className="menu__master-online-description">
                                                {busyCount} <span className="menu__master-online-total">/ {onlineCount}</span>
                                            </p>
                                        </div>
                                    </div>

                                    {loadError && <p className="menu__hint menu__hint--error">{loadError}</p>}

                                    <div className="menu__masters">
                                        <div className="menu__masters--info">
                                            <h2 className="menu__masters-title">МАСТЕРА ({engineersList.length})</h2>
                                            <div className="menu__masters-actions">
                                                <button className={`menu__masters-button${noDistrict ? ' menu__button--disabled' : ''}`}
                                                        disabled={noDistrict} onClick={() => setIsCreateOpen(true)}>
                                                    + Добавить мастера
                                                </button>
                                                <span> | </span>
                                                <button className={`menu__masters-button menu__masters-button--secondary${noDistrict ? ' menu__button--disabled' : ''}`}
                                                        disabled={noDistrict} onClick={() => setIsEqListOpen(true)}>
                                                    + Оборудование
                                                </button>
                                            </div>
                                        </div>
                                        <div className="menu__masters-cards scroll-area">
                                            {engineersList.length === 0 && !loading && <p className="menu__hint">Мастеров пока нет</p>}
                                            {engineersList.map((m) => (
                                                <article key={m.id}
                                                         className={m.online ? 'menu__masters-card' : 'menu__masters-card--disabled'}
                                                         onClick={() => setMenuEngineerId(m.id)} style={{ cursor: 'pointer' }}>
                                                    <div className="menu__masters-card-head">
                                                        <h3 className={m.online ? 'menu__masters-card-title'
                                                            : 'menu__masters-card-title menu__masters-card-title--disabled'}>
                                                            {m.name} ({m.mode})
                                                        </h3>
                                                        <div className="menu__masters-card-actions"
                                                             onClick={(e) => e.stopPropagation()}>
                                                            <button type="button" className="menu__map-btn"
                                                                    onClick={(e) => openEngineerMap(m.id, e)}>
                                                                ↗️ Карта
                                                            </button>
                                                        </div>
                                                    </div>
                                                    <p className={m.online ? 'menu__masters-card-description'
                                                        : 'menu__masters-card-description menu__masters-card-description--disabled'}>
                                                        Смена: {m.shift} | Заявок: {m.requests}
                                                    </p>
                                                </article>
                                            ))}
                                        </div>
                                    </div>

                                    <div className="menu__applications">
                                        <div className="menu__applications-title-row">
                                            <h2 className="menu__applications-title">
                                                ЗАЯВКИ ({unallocatedList.length + plannedListRaw.length + cancelledList.length})
                                            </h2>
                                            <div className="menu__sort">
                                                <span className="menu__sort-label">Сортировка:</span>
                                                <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}
                                                        className="menu__sort-select">
                                                    <option value="none">По умолчанию</option>
                                                    <option value={SORT_BY_TYPE}>По типу</option>
                                                    <option value={SORT_BY_ENGINEER}>По мастеру</option>
                                                </select>
                                            </div>
                                            {plannedListRaw.length > 0 && (
                                                <button type="button" className="menu__applications-reset"
                                                        onClick={handleResetAllRequests} disabled={resetting}>
                                                    {resetting ? 'Сброс…' : 'Сбросить заявки'}
                                                </button>
                                            )}
                                        </div>

                                        <div className="menu__applications-buttons-choice">
                                            <div className="menu__unallocated-applications-buttons">
                                                <button className={
                                                    tab === 'unallocated'
                                                        ? 'menu__unallocated-applications-button'
                                                        : 'menu__unallocated-applications-button menu__no-active-applications-button'
                                                } onClick={() => { setTab('unallocated'); setActiveRequestId(null) }}>
                                                    Не распределённые
                                                </button>
                                                <p className={'menu__unallocated-applications-quantity ' +
                                                    (tab === 'unallocated' ? 'menu__applications-quantity--active'
                                                                           : 'menu__applications-quantity--inactive')}>
                                                    {unallocatedList.length}
                                                </p>
                                            </div>

                                            <div className="menu__distributed-applications-buttons">
                                                <button className={
                                                    tab === 'distributed'
                                                        ? 'menu__distributed-applications-button'
                                                        : 'menu__distributed-applications-button menu__no-active-applications-button'
                                                } onClick={() => { setTab('distributed'); setActiveUnallocatedId(null) }}>
                                                    Распределённые
                                                </button>
                                                <p className={'menu__distributed-applications-quantity ' +
                                                    (tab === 'distributed' ? 'menu__applications-quantity--active'
                                                                           : 'menu__applications-quantity--inactive')}>
                                                    {plannedListRaw.length}
                                                </p>
                                            </div>

                                            <div className="menu__cancelled-applications-buttons">
                                                <button className={
                                                    tab === 'cancelled'
                                                        ? 'menu__cancelled-applications-button'
                                                        : 'menu__cancelled-applications-button menu__no-active-applications-button'
                                                } onClick={() => { setTab('cancelled'); setActiveUnallocatedId(null); setActiveRequestId(null) }}>
                                                    Отменённые клиентом
                                                </button>
                                                <p className={'menu__cancelled-applications-quantity ' +
                                                    (tab === 'cancelled' ? 'menu__applications-quantity--active-red'
                                                                         : 'menu__applications-quantity--inactive')}>
                                                    {cancelledList.length}
                                                </p>
                                            </div>
                                        </div>

                                        {tab === 'unallocated' && (
                                            <div className="menu__unallocated-cards scroll-area">
                                                {sortedUnallocated.map((r) => (
                                                    <UnallocatedCard
                                                        key={r.id}
                                                        request={r}
                                                        isActive={r.id === activeUnallocatedId}
                                                        mode="unallocated"
                                                        onSelect={handleSelectUnallocated}
                                                        onAssignMaster={handleAssignMasterUnallocated}
                                                        onClientCancel={handleClientCancelUnallocated}
                                                        onEditCoords={(req) => setCoordsEditReq(req)}
                                                    />
                                                ))}
                                            </div>
                                        )}

                                        {tab === 'distributed' && (
                                            <div className="menu__distributed-cards scroll-area">
                                                {sortedPlanned.length === 0 && !loading && (
                                                    <p className="menu__hint menu__hint--center">Нет распределённых заявок</p>
                                                )}
                                                {sortedPlanned.map((r) => {
                                                    const isActive = r.id === activeRequestId
                                                    const engName = engineers[r.engineer_id]?.name
                                                    const seq = seqByRequest[r.id]
                                                    return (
                                                        <DistributedCard
                                                            key={r.id}
                                                            request={r}
                                                            engineerName={engName}
                                                            seq={seq}
                                                            isActive={isActive}
                                                            busy={statusBusy}
                                                            cardRef={isActive ? activeCardRef : null}
                                                            onSelect={handleSelectDistributed}
                                                            onChangeStatus={handleStatusChange}
                                                            onCancelRequest={handleCancelRequest}
                                                            onChangeMaster={(req) => setReassignRequest(req)}
                                                        />
                                                    )
                                                })}
                                            </div>
                                        )}

                                        {tab === 'cancelled' && (
                                            <div className="menu__unallocated-cards scroll-area">
                                                {cancelledList.length === 0 && !loading && (
                                                    <p className="menu__hint menu__hint--center">
                                                        Отменённых заявок на эту дату нет
                                                    </p>
                                                )}
                                                {sortedCancelled.map((r) => (
                                                    <UnallocatedCard
                                                        key={r.id}
                                                        request={r}
                                                        isActive={false}
                                                        mode="cancelled"
                                                        onRestore={handleRestoreCancelled}
                                                    />
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </main>
                        </div>
                    </section>
                </div>

                {mapPanelUrl && iframeSrc && (
                    <aside className="dispatcher__map-panel">
                        <div className="dispatcher__map-header">
                            <div className="dispatcher__map-title" title={mapPanelTitle}>{mapPanelTitle || 'Карта'}</div>
                            <div className="dispatcher__map-actions">
                                <button
                                    type="button"
                                    className="dispatcher__map-btn"
                                    onClick={handleManualRefreshMap}
                                    disabled={mapRefreshing}>
                                    {mapRefreshing ? '⟳ Обновление…' : '⟳ Обновить'}
                                </button>
                                <button
                                    type="button"
                                    className="dispatcher__map-btn"
                                    onClick={handleShowAllMap}>
                                    Все мастера
                                </button>
                                <button
                                    type="button"
                                    className="dispatcher__map-close"
                                    onClick={closeMapPanel}
                                    aria-label="Закрыть карту">
                                    ×
                                </button>
                            </div>
                        </div>
                        <iframe
                            key={iframeSrc}
                            className="dispatcher__map-frame"
                            src={iframeSrc}
                            title="map"
                        />
                    </aside>
                )}
            </div>

            <ChoiceDistrictModal isOpen={isDistrictOpen} onClose={() => setIsDistrictOpen(false)}
                                 onSelect={handleSelectDistrict} selectedId={district?.id} />

            <ReassignModal
                isOpen={!!reassignRequest}
                request={reassignRequest}
                districtId={district?.id}
                visitDate={visitDate}
                onClose={() => setReassignRequest(null)}
                onAssign={handleAssign}
            />

            <EngineerMenuModal isOpen={!!menuEngineerId} engineerId={menuEngineerId}
                               onClose={() => setMenuEngineerId(null)} onChanged={refresh} />

            <UrgentRequestModal isOpen={isUrgentOpen}
                                onClose={() => setIsUrgentOpen(false)}
                                onSubmit={async (data) => {
                                    const res = await createUrgentRequest({ ...data, district_id: district.id })
                                    await refresh()
                                    await refreshMapsAfterChange()
                                    if (res?.auto_assigned && res?.engineer_name) {
                                        showToast(
                                            `Срочная заявка назначена мастеру ${res.engineer_name}`,
                                            'success', 5000,
                                        )
                                    } else {
                                        showToast(
                                            'Срочная заявка создана и ушла в нераспределённые',
                                            'warning', 5000,
                                        )
                                    }
                                    return res
                                }} />

            <EditCoordsModal isOpen={!!coordsEditReq} request={coordsEditReq}
                             onClose={() => setCoordsEditReq(null)}
                             onSave={handleSaveCoords} />

            <EngineerFormModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)}
                               districtId={district?.id}
                               onSubmit={async (data) => {
                                   try {
                                       await createEngineer(data)
                                       await refresh()
                                       setIsCreateOpen(false)
                                       showToast('Мастер добавлен', 'success')
                                   } catch (e) {
                                       console.error(e)
                                       showToast('Не удалось добавить мастера', 'error')
                                   }
                               }} />

            <EquipmentListModal isOpen={isEqListOpen} onClose={() => setIsEqListOpen(false)}
                                onChanged={refresh}
                                onCreateNew={() => { setIsEqListOpen(false); setIsEqCreateOpen(true) }} />

            <EquipmentFormModal isOpen={isEqCreateOpen} onClose={() => setIsEqCreateOpen(false)}
                                onSubmit={async (data) => {
                                    try {
                                        await createEquipment(data)
                                        setIsEqCreateOpen(false)
                                        setIsEqListOpen(true)
                                        showToast('Оборудование добавлено', 'success')
                                    } catch (e) {
                                        console.error(e)
                                        showToast('Не удалось добавить оборудование', 'error')
                                    }
                                }} />

            <IncomingRequestToast toasts={incoming} onAccept={handleAcceptIncoming} onDismiss={handleDismissIncoming} />

            <Toast toasts={toasts} onDismiss={dismissToast} />
        </main>
    )
}

export default DispatcherPage