import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import {
    getEngineerDetails,
    updateEngineer,
    endShift,
    startShift,
    listEquipment,
    issueEquipment,
    returnEquipment,
    clearEngineerEquip,
} from '../../api/dispatcher'
import './EngineerMenuModal.css'

const TRANSPORT_OPTIONS = ['Пеший', 'Велосипед', 'Автомобиль']

const WORK_TYPES = [
    { value: 'Подключение',         label: 'Подключение' },
    { value: 'Локальная заявка',    label: 'Локальная заявка' },
    { value: 'Дозаказ',             label: 'Дозаказ' },
    { value: 'Глобальная проблема', label: 'Глобальная проблема' },
]

const initials = (name = '') =>
    name.split(' ').filter(Boolean).slice(0, 2).map((s) => s[0]).join('').toUpperCase()

const EngineerMenuModal = ({ isOpen, engineerId, onClose, onChanged }) => {
    const [data, setData]       = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError]     = useState(null)
    const [editMode, setEditMode] = useState(false)
    const [saving, setSaving]   = useState(false)
    const [busy, setBusy]       = useState(false)
    const [form, setForm]       = useState(null)

    // причина снятия со смены
    const [reasonOpen, setReasonOpen] = useState(false)
    const [reason, setReason] = useState('')
    const [reasonError, setReasonError] = useState(null)

    // выдача оборудования
    const [issueOpen, setIssueOpen] = useState(false)
    const [catalog, setCatalog] = useState([])
    const [pickId, setPickId] = useState('')
    const [pickQty, setPickQty] = useState(1)
    const [issueError, setIssueError] = useState(null)

    // возврат конкретной позиции
    const [returnItem, setReturnItem] = useState(null)
    const [returnQty, setReturnQty]   = useState(1)
    const [returnError, setReturnError] = useState(null)

    useEffect(() => {
        if (!isOpen || !engineerId) return
        let cancelled = false
        setLoading(true); setError(null); setEditMode(false)
        setReasonOpen(false); setReason(''); setReasonError(null)
        setIssueOpen(false); setIssueError(null)
        setReturnItem(null); setReturnQty(1); setReturnError(null)

        getEngineerDetails(engineerId)
            .then((d) => {
                if (cancelled) return
                setData(d)
                setForm({
                    fio: d.name,
                    phone: d.phone || '',
                    transport: d.transport_label,
                    shift_start: d.shift_start || '08:00',
                    shift_end: d.shift_end || '17:00',
                    skills: d.skills || [],
                })
            })
            .catch((e) => { if (!cancelled) setError(e.message) })
            .finally(() => { if (!cancelled) setLoading(false) })
        return () => { cancelled = true }
    }, [isOpen, engineerId])

    useEffect(() => {
        if (!issueOpen) return
        listEquipment()
            .then((d) => {
                setCatalog(d.equipment ?? [])
                setPickId(d.equipment?.[0]?.id ?? '')
                setPickQty(1)
                setIssueError(null)
            })
            .catch((e) => setIssueError(e.message))
    }, [issueOpen])

    if (!isOpen) return null

    const setField = (name, value) =>
        setForm((prev) => ({ ...prev, [name]: value }))

    const toggleSkill = (value) => {
        setForm((prev) => {
            const has = prev.skills.includes(value)
            return {
                ...prev,
                skills: has ? prev.skills.filter((s) => s !== value) : [...prev.skills, value],
            }
        })
    }

    const reload = async () => {
        const fresh = await getEngineerDetails(engineerId)
        setData(fresh)
    }

    const handleSave = async () => {
        setSaving(true)
        try {
            await updateEngineer(engineerId, form)
            await reload()
            setEditMode(false)
            onChanged?.()
        } catch (e) {
            setError(e.message)
        } finally {
            setSaving(false)
        }
    }

    const openEndShift = () => {
        setReason(''); setReasonError(null); setReasonOpen(true)
    }
    const submitEndShift = async () => {
        if (!reason.trim()) { setReasonError('Укажите причину'); return }
        setBusy(true)
        try {
            await endShift(engineerId, reason.trim())
            await reload()
            setReasonOpen(false)
            onChanged?.()
        } catch (e) { setReasonError(e.message) }
        finally { setBusy(false) }
    }

    const handleStartShift = async () => {
        setBusy(true)
        try {
            await startShift(engineerId)
            await reload()
            onChanged?.()
        } catch (e) { setError(e.message) }
        finally { setBusy(false) }
    }

    const submitIssue = async () => {
        if (!pickId || pickQty < 1) { setIssueError('Выберите оборудование и количество'); return }
        try {
            await issueEquipment(engineerId, pickId, pickQty)
            await reload()
            setIssueOpen(false)
            onChanged?.()
        } catch (e) { setIssueError(e.message) }
    }

    const openReturn = (eq) => {
        setReturnItem(eq); setReturnQty(1); setReturnError(null)
    }
    const submitReturn = async () => {
        if (!returnItem) return
        if (returnQty < 1) { setReturnError('Количество должно быть больше 0'); return }
        if (returnQty > returnItem.count) { setReturnError(`У инженера только ${returnItem.count} шт`); return }
        try {
            await returnEquipment(engineerId, returnItem.id, returnQty)
            await reload()
            setReturnItem(null)
            onChanged?.()
        } catch (e) { setReturnError(e.message) }
    }
    const submitReturnAll = async (eq) => {
        try {
            await returnEquipment(engineerId, eq.id, eq.count)
            await reload()
            onChanged?.()
        } catch (e) { setError(e.message) }
    }

    const handleClearAll = async () => {
        if (!window.confirm('Забрать всё оборудование у инженера?')) return
        try {
            await clearEngineerEquip(engineerId)
            await reload()
            onChanged?.()
        } catch (e) { setError(e.message) }
    }

    const handleClose = () => {
        setEditMode(false); setReasonOpen(false); setIssueOpen(false); setReturnItem(null)
        onClose()
    }

    return createPortal(
        <main
            className="eng-modal__page"
            style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(15,23,42,0.55)' }}
            onClick={handleClose}>
            <section className="eng-modal" onClick={(e) => e.stopPropagation()}>

                {loading && <div className="eng-modal__loading">Загрузка…</div>}
                {error && <div className="eng-modal__error">{error}</div>}

                {data && !loading && (
                    <>
                        <header className="eng-modal__header">
                            <div className="eng-modal__avatar">
                                <span>{initials(data.name)}</span>
                                {data.on_shift && <span className="eng-modal__avatar-dot" />}
                            </div>
                            <div className="eng-modal__title-wrap">
                                <h2 className="eng-modal__title">{data.name}</h2>
                                <p className="eng-modal__subtitle">
                                    {data.role_title} • {data.transport_label}
                                </p>
                            </div>
                            <button
                                type="button"
                                className="eng-modal__close"
                                onClick={handleClose}
                                aria-label="Закрыть">
                                <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                                    <path d="M1.08 15.36 0 14.28 6.56 7.68 0 1.08 1.08 0 7.64 6.6 14.16 0l1.08 1.08L8.68 7.68l6.56 6.6-1.08 1.08L7.64 8.8 1.08 15.36Z" fill="#94A3B8"/>
                                </svg>
                            </button>
                        </header>

                        <div className="eng-modal__body">
                            <div className="eng-modal__left">
                                <div className="eng-modal__block">
                                    <div className="eng-modal__block-title">СТАТУС СМЕНЫ</div>
                                    <div className={
                                        'eng-modal__shift-badge ' +
                                        (data.on_shift
                                            ? 'eng-modal__shift-badge--active'
                                            : 'eng-modal__shift-badge--off')
                                    }>
                                        <span className="eng-modal__shift-dot" />
                                        {data.shift_label}
                                    </div>
                                    {!data.on_shift && data.off_shift_reason && (
                                        <p className="eng-modal__off-reason">
                                            Причина: {data.off_shift_reason}
                                        </p>
                                    )}

                                    {editMode ? (
                                        <div className="eng-modal__row">
                                            <label>Начало
                                                <input className="eng-modal__input" type="time"
                                                    value={form.shift_start}
                                                    onChange={(e) => setField('shift_start', e.target.value)} />
                                            </label>
                                            <label>Конец
                                                <input className="eng-modal__input" type="time"
                                                    value={form.shift_end}
                                                    onChange={(e) => setField('shift_end', e.target.value)} />
                                            </label>
                                        </div>
                                    ) : (
                                        <div className="eng-modal__field">
                                            <span className="eng-modal__field-label">Локация:</span>
                                            <span className="eng-modal__field-value">
                                                {data.location || '—'}
                                            </span>
                                        </div>
                                    )}
                                </div>

                                <div className="eng-modal__block eng-modal__block--grow">
                                    <div className="eng-modal__block-title">
                                        ЗАЯВКИ НА СЕГОДНЯ ({data.today_orders.length})
                                    </div>
                                    <div className="eng-modal__orders">
                                        {data.today_orders.length === 0 && (
                                            <p className="eng-modal__empty">Заявок нет</p>
                                        )}
                                        {data.today_orders.map((o) => (
                                            <div key={o.id} className="eng-modal__order">
                                                <div className="eng-modal__order-title">
                                                    #{o.short_id} - {o.address}
                                                </div>
                                                <div className="eng-modal__order-sub">
                                                    {o.status_label} {o.eta || o.window || ''}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            <div className="eng-modal__right">
                                {editMode ? (
                                    <div className="eng-modal__block">
                                        <div className="eng-modal__block-title">ИНФОРМАЦИЯ</div>
                                        <label className="eng-modal__edit-field">
                                            ФИО
                                            <input className="eng-modal__input" type="text"
                                                value={form.fio}
                                                onChange={(e) => setField('fio', e.target.value)} />
                                        </label>
                                        <label className="eng-modal__edit-field">
                                            Телефон
                                            <input className="eng-modal__input" type="tel"
                                                value={form.phone}
                                                onChange={(e) => setField('phone', e.target.value)} />
                                        </label>
                                        <label className="eng-modal__edit-field">
                                            Транспорт
                                            <select className="eng-modal__input"
                                                value={form.transport}
                                                onChange={(e) => setField('transport', e.target.value)}>
                                                {TRANSPORT_OPTIONS.map((t) => (
                                                    <option key={t} value={t}>{t}</option>
                                                ))}
                                            </select>
                                        </label>
                                        <label className="eng-modal__edit-field">
                                            Навыки
                                            <div className="eng-modal__skills">
                                                {WORK_TYPES.map((w) => {
                                                    const active = form.skills.includes(w.value)
                                                    return (
                                                        <button key={w.value} type="button"
                                                            className={
                                                                'eng-modal__skill' +
                                                                (active ? ' eng-modal__skill--active' : '')
                                                            }
                                                            onClick={() => toggleSkill(w.value)}>
                                                            {w.label}
                                                        </button>
                                                    )
                                                })}
                                            </div>
                                        </label>
                                    </div>
                                ) : (
                                    <div className="eng-modal__block eng-modal__block--grow">
                                        <div className="eng-modal__block-head">
                                            <div>
                                                <div className="eng-modal__block-title">
                                                    ОБОРУДОВАНИЕ У ИНЖЕНЕРА
                                                </div>
                                                <div className="eng-modal__block-subtitle">
                                                    УСТРОЙСТВА И ТЕРМИНАЛЫ
                                                </div>
                                            </div>
                                            {data.equipment.length > 0 && (
                                                <button
                                                    type="button"
                                                    className="eng-modal__mini-btn eng-modal__mini-btn--danger"
                                                    onClick={handleClearAll}>
                                                    Забрать всё
                                                </button>
                                            )}
                                        </div>
                                        <div className="eng-modal__equipment">
                                            {data.equipment.length === 0 && (
                                                <p className="eng-modal__empty">
                                                    Оборудование не выдано
                                                </p>
                                            )}
                                            {data.equipment.map((eq) => (
                                                <div key={eq.id} className="eng-modal__equipment-item">
                                                    <div className="eng-modal__equipment-info">
                                                        <div className="eng-modal__equipment-name">{eq.name}</div>
                                                        <div className="eng-modal__equipment-meta">
                                                            S/N: {eq.serial} • Состояние: {eq.state}
                                                        </div>
                                                    </div>
                                                    <div className="eng-modal__equipment-actions">
                                                        <div className="eng-modal__equipment-count">
                                                            {eq.count} шт
                                                        </div>
                                                        <div className="eng-modal__equipment-buttons">
                                                            <button
                                                                type="button"
                                                                className="eng-modal__mini-btn"
                                                                onClick={() => openReturn(eq)}>
                                                                Вернуть
                                                            </button>
                                                            <button
                                                                type="button"
                                                                className="eng-modal__mini-btn eng-modal__mini-btn--danger"
                                                                onClick={() => submitReturnAll(eq)}>
                                                                Забрать всё
                                                            </button>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        <footer className="eng-modal__footer">
                            {!editMode && (
                                <button className="eng-modal__btn eng-modal__btn--outline"
                                    onClick={() => setEditMode(true)}>
                                    Изменить<br />информацию
                                </button>
                            )}
                            {!editMode && (
                                <button className="eng-modal__btn eng-modal__btn--outline"
                                    onClick={() => setIssueOpen(true)}>
                                    Выдать<br />оборудование
                                </button>
                            )}

                            {data.on_shift ? (
                                <button className="eng-modal__btn eng-modal__btn--danger"
                                    onClick={openEndShift} disabled={busy}>
                                    Снять со<br />смены
                                </button>
                            ) : (
                                <button className="eng-modal__btn eng-modal__btn--success"
                                    onClick={handleStartShift} disabled={busy}>
                                    Вернуть<br />на смену
                                </button>
                            )}

                            {editMode && (
                                <button className="eng-modal__btn eng-modal__btn--dark"
                                    onClick={handleSave} disabled={saving}>
                                    {saving ? 'Сохранение…' : 'Сохранить изменения'}
                                </button>
                            )}
                        </footer>

                        {reasonOpen && (
                            <div className="eng-modal__reason-overlay"
                                onClick={(e) => e.stopPropagation()}>
                                <div className="eng-modal__reason">
                                    <h3 className="eng-modal__reason-title">Снять со смены</h3>
                                    <p className="eng-modal__reason-subtitle">{data.name}</p>
                                    <label className="eng-modal__edit-field">
                                        Причина
                                        <textarea
                                            className="eng-modal__input eng-modal__textarea"
                                            rows={3}
                                            value={reason}
                                            onChange={(e) => { setReason(e.target.value); setReasonError(null) }}
                                            placeholder="Например: поломка авто, конец смены"
                                            autoFocus
                                        />
                                    </label>
                                    {reasonError && <p className="eng-modal__error">{reasonError}</p>}
                                    <div className="eng-modal__reason-actions">
                                        <button type="button" className="eng-modal__btn eng-modal__btn--danger"
                                            onClick={submitEndShift} disabled={busy}>
                                            {busy ? 'Снятие…' : 'Снять со смены'}
                                        </button>
                                        <button type="button" className="eng-modal__btn eng-modal__btn--outline"
                                            onClick={() => setReasonOpen(false)} disabled={busy}>
                                            Отмена
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}

                        {issueOpen && (
                            <div className="eng-modal__reason-overlay"
                                onClick={(e) => e.stopPropagation()}>
                                <div className="eng-modal__reason">
                                    <h3 className="eng-modal__reason-title">Выдать оборудование</h3>
                                    <p className="eng-modal__reason-subtitle">{data.name}</p>

                                    <label className="eng-modal__edit-field">
                                        Оборудование
                                        <select className="eng-modal__input"
                                            value={pickId}
                                            onChange={(e) => setPickId(e.target.value)}>
                                            {catalog.map((eq) => (
                                                <option key={eq.id} value={eq.id}>
                                                    {eq.name} (на складе: {eq.quantity})
                                                </option>
                                            ))}
                                        </select>
                                    </label>

                                    <label className="eng-modal__edit-field">
                                        Количество
                                        <input className="eng-modal__input" type="number" min={1}
                                            value={pickQty}
                                            onChange={(e) => setPickQty(Number(e.target.value) || 1)} />
                                    </label>

                                    {issueError && <p className="eng-modal__error">{issueError}</p>}

                                    <div className="eng-modal__reason-actions">
                                        <button type="button" className="eng-modal__btn eng-modal__btn--dark"
                                            onClick={submitIssue}>
                                            Выдать
                                        </button>
                                        <button type="button" className="eng-modal__btn eng-modal__btn--outline"
                                            onClick={() => setIssueOpen(false)}>
                                            Отмена
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}

                        {returnItem && (
                            <div className="eng-modal__reason-overlay"
                                onClick={(e) => e.stopPropagation()}>
                                <div className="eng-modal__reason">
                                    <h3 className="eng-modal__reason-title">Вернуть на склад</h3>
                                    <p className="eng-modal__reason-subtitle">
                                        {returnItem.name} — у инженера {returnItem.count} шт
                                    </p>
                                    <label className="eng-modal__edit-field">
                                        Количество
                                        <input className="eng-modal__input" type="number"
                                            min={1} max={returnItem.count}
                                            value={returnQty}
                                            onChange={(e) => setReturnQty(Number(e.target.value) || 1)} />
                                    </label>
                                    {returnError && <p className="eng-modal__error">{returnError}</p>}
                                    <div className="eng-modal__reason-actions">
                                        <button type="button" className="eng-modal__btn eng-modal__btn--dark"
                                            onClick={submitReturn}>
                                            Вернуть
                                        </button>
                                        <button type="button" className="eng-modal__btn eng-modal__btn--outline"
                                            onClick={() => setReturnItem(null)}>
                                            Отмена
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </section>
        </main>,
        document.body,
    )
}

export default EngineerMenuModal