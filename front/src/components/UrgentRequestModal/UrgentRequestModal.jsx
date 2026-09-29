import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import './UrgentRequestModal.css'

const ALL_REQUEST_TYPES = [
    { value: 'connection', label: 'Подключение' },
    { value: 'local',      label: 'Локальная заявка' },
    { value: 'reorder',    label: 'Дозаказ' },
    { value: 'global',     label: 'Глобальная проблема' },
]
const NORMAL_REQUEST_TYPES = ALL_REQUEST_TYPES.filter((t) => t.value !== 'global')

const pad = (n) => String(n).padStart(2, '0')
const nowHHMM = () => { const d = new Date(); return `${pad(d.getHours())}:${pad(d.getMinutes())}` }
const plus2hHHMM = () => { const d = new Date(Date.now() + 2*60*60*1000); return `${pad(d.getHours())}:${pad(d.getMinutes())}` }

const EMPTY = {
    priority: 'urgent',
    client_name: '',
    client_phone: '',
    city: '', street: '', house: '', building: '',
    entrance: '', floor: '', apartment: '',
    request_type: 'global',
    window_start: nowHHMM(),
    window_end:   plus2hHHMM(),
}

const UrgentRequestModal = ({ isOpen, onClose, onSubmit }) => {
    const [form, setForm] = useState(EMPTY)
    const [errors, setErrors] = useState({})
    const [lastNormalType, setLastNormalType] = useState('local')
    const [submitting, setSubmitting] = useState(false)
    const [geoResult, setGeoResult] = useState(null)   // { ok: bool, address }

    useEffect(() => {
        if (isOpen) {
            setForm({ ...EMPTY, window_start: nowHHMM(), window_end: plus2hHHMM() })
            setErrors({})
            setLastNormalType('local')
            setSubmitting(false)
            setGeoResult(null)
        }
    }, [isOpen])

    if (!isOpen) return null

    const isUrgent = form.priority === 'urgent'

    const setField = (name, value) => {
        setForm((prev) => ({ ...prev, [name]: value }))
        if (errors[name]) setErrors((prev) => ({ ...prev, [name]: undefined }))
    }

    const setPriority = (value) => {
        setErrors({})
        if (value === 'urgent') {
            setForm((prev) => {
                if (prev.request_type !== 'global') setLastNormalType(prev.request_type)
                return { ...prev, priority: 'urgent', request_type: 'global' }
            })
        } else {
            setForm((prev) => {
                let nextType = prev.request_type
                if (nextType === 'global') {
                    nextType = NORMAL_REQUEST_TYPES.some((t) => t.value === lastNormalType)
                        ? lastNormalType : 'local'
                }
                return { ...prev, priority: 'normal', request_type: nextType }
            })
        }
    }

    const validate = () => {
        const e = {}
        if (!form.city.trim())   e.city = 'Укажите город'
        if (!form.street.trim()) e.street = 'Укажите улицу'
        if (!form.house.trim())  e.house = 'Укажите дом'
        if (!isUrgent) {
            if (!form.window_start) e.window_start = 'Укажите начало окна'
            if (!form.window_end)   e.window_end = 'Укажите конец окна'
            if (form.window_start && form.window_end && form.window_start >= form.window_end) {
                e.window_end = 'Конец окна должен быть позже начала'
            }
        }
        setErrors(e)
        return Object.keys(e).length === 0
    }

    const handleSubmit = async (ev) => {
        ev.preventDefault()
        if (submitting) return
        if (!validate()) return

        const houseWithBuilding =
            form.house && form.building ? `${form.house}к${form.building}` : form.house
        const addressParts = [form.city, form.street, houseWithBuilding].filter(Boolean)
        const requestTypeLabel =
            ALL_REQUEST_TYPES.find((t) => t.value === form.request_type)?.label ?? 'Локальная заявка'

        const ws = isUrgent ? nowHHMM() : form.window_start
        const we = isUrgent ? plus2hHHMM() : form.window_end

        setSubmitting(true)
        setGeoResult({ ok: null, address: addressParts.join(', ') })   // «идёт геокодирование»

        try {
            const res = await onSubmit?.({
                priority: form.priority,
                client_name: form.client_name,
                client_phone: form.client_phone,
                service: requestTypeLabel,
                request_type: form.request_type,
                address: addressParts.join(', '),
                window: `${ws} — ${we}`,
                window_start: ws,
                window_end:   we,
                city: form.city, street: form.street, house: form.house,
                building: form.building, entrance: form.entrance,
                floor: form.floor, apartment: form.apartment,
            })

            // если фронт-обёртка вернула { geocoded }
            const ok = res?.geocoded === true
            setGeoResult({ ok, address: addressParts.join(', ') })

            if (ok) {
                // всё хорошо — закрываем через 700мс, чтобы пользователь увидел галочку
                setTimeout(() => { onClose?.() }, 700)
            }
            // если ok=false — не закрываем, показываем ошибку под полем адреса
        } catch (err) {
            setGeoResult({ ok: false, address: addressParts.join(', '), error: err?.message })
        } finally {
            setSubmitting(false)
        }
    }

    const geoState = geoResult?.ok
    const showGeoProgress = submitting && geoResult?.ok === null

    return createPortal(
        <main className="urgent-modal__page"
              style={{ position:'fixed', inset:0, zIndex:1000, background:'rgba(15,23,42,0.55)' }}
              onClick={() => !submitting && onClose?.()}>
            <section className="urgent-modal" onClick={(e) => e.stopPropagation()}>
                <header className="urgent-modal__header">
                    <div className="urgent-modal__title-wrap">
                        <div className="urgent-modal__badge">!</div>
                        <div>
                            <h2 className="urgent-modal__title">Создание заявки</h2>
                            <p className="urgent-modal__subtitle">
                                Аварийный ввод задачи с автоматическим пересчетом маршрута
                            </p>
                        </div>
                    </div>
                    <button type="button" className="urgent-modal__close"
                            onClick={() => !submitting && onClose?.()} aria-label="Закрыть">
                        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                            <path d="M1.08 15.36 0 14.28 6.56 7.68 0 1.08 1.08 0 7.64 6.6 14.16 0l1.08 1.08L8.68 7.68l6.56 6.6-1.08 1.08L7.64 8.8 1.08 15.36Z" fill="#94A3B8"/>
                        </svg>
                    </button>
                </header>

                <form className="urgent-modal__body" onSubmit={handleSubmit}>
                    <div className="urgent-modal__field">
                        <label className="urgent-modal__label">УРОВЕНЬ ПРИОРИТЕТА</label>
                        <div className="urgent-modal__priority">
                            <button type="button"
                                className={'urgent-modal__priority-btn' + (form.priority === 'urgent' ? ' urgent-modal__priority-btn--active' : '')}
                                onClick={() => setPriority('urgent')} disabled={submitting}>
                                <span className="urgent-modal__priority-dot" />
                                Высокий (авария)
                            </button>
                            <button type="button"
                                className={'urgent-modal__priority-btn' + (form.priority === 'normal' ? ' urgent-modal__priority-btn--active' : '')}
                                onClick={() => setPriority('normal')} disabled={submitting}>
                                Низкий
                            </button>
                        </div>
                    </div>

                    <div className="urgent-modal__field">
                        <label className="urgent-modal__label">Имя клиента</label>
                        <input className="urgent-modal__input" type="text"
                            value={form.client_name}
                            onChange={(e) => setField('client_name', e.target.value)}
                            placeholder="Иван Иванов" disabled={submitting}/>
                    </div>

                    <div className="urgent-modal__field">
                        <label className="urgent-modal__label">Номер телефона</label>
                        <input className="urgent-modal__input" type="tel"
                            value={form.client_phone}
                            onChange={(e) => setField('client_phone', e.target.value)}
                            placeholder="+7 (___) ___-__-__" disabled={submitting}/>
                    </div>

                    <div className="urgent-modal__field">
                        <label className="urgent-modal__label">Адрес объекта *</label>
                        <div className="urgent-modal__grid urgent-modal__grid--address">
                            <input className="urgent-modal__input" placeholder="Город *"
                                value={form.city} onChange={(e) => setField('city', e.target.value)} disabled={submitting}/>
                            <input className="urgent-modal__input" placeholder="Улица *"
                                value={form.street} onChange={(e) => setField('street', e.target.value)} disabled={submitting}/>
                            <input className="urgent-modal__input" placeholder="Дом *"
                                value={form.house} onChange={(e) => setField('house', e.target.value)} disabled={submitting}/>
                            <input className="urgent-modal__input" placeholder="Корпус"
                                value={form.building} onChange={(e) => setField('building', e.target.value)} disabled={submitting}/>
                            <input className="urgent-modal__input" placeholder="Подъезд"
                                value={form.entrance} onChange={(e) => setField('entrance', e.target.value)} disabled={submitting}/>
                            <input className="urgent-modal__input" placeholder="Этаж"
                                value={form.floor} onChange={(e) => setField('floor', e.target.value)} disabled={submitting}/>
                            <input className="urgent-modal__input" placeholder="Квартира"
                                value={form.apartment} onChange={(e) => setField('apartment', e.target.value)} disabled={submitting}/>
                        </div>

                        {(errors.city || errors.street || errors.house) && (
                            <p className="urgent-modal__error">
                                {errors.city || errors.street || errors.house}
                            </p>
                        )}

                        {showGeoProgress && (
                            <p className="urgent-modal__geo urgent-modal__geo--progress">
                                <span className="urgent-modal__geo-spinner" />
                                Геокодируем адрес…
                            </p>
                        )}
                        {!submitting && geoState === true && (
                            <p className="urgent-modal__geo urgent-modal__geo--ok">
                                ✓ Адрес геокодирован
                            </p>
                        )}
                        {!submitting && geoState === false && (
                            <p className="urgent-modal__geo urgent-modal__geo--fail">
                                ✗ Не удалось геокодировать. Заявка уйдёт в нераспределённые —
                                координаты можно будет задать вручную.
                            </p>
                        )}
                    </div>

                    <div className="urgent-modal__field">
                        <label className="urgent-modal__label">Тип заявки</label>
                        <select
                            className="urgent-modal__input urgent-modal__select"
                            value={form.request_type}
                            disabled={isUrgent || submitting}
                            onChange={(e) => setField('request_type', e.target.value)}
                            style={isUrgent ? { background:'#F8FAFC', color:'#64748B', cursor:'not-allowed' } : undefined}>
                            {(isUrgent ? ALL_REQUEST_TYPES : NORMAL_REQUEST_TYPES).map((t) => (
                                <option key={t.value} value={t.value}>{t.label}</option>
                            ))}
                        </select>
                        {isUrgent && (
                            <p className="urgent-modal__hint">
                                Для аварийной заявки тип всегда «Глобальная проблема»
                            </p>
                        )}
                    </div>

                    {!isUrgent ? (
                        <div className="urgent-modal__field">
                            <label className="urgent-modal__label">Окно времени</label>
                            <div className="urgent-modal__grid urgent-modal__grid--time">
                                <div>
                                    <span className="urgent-modal__sublabel">Начало</span>
                                    <input className="urgent-modal__input" type="time"
                                        value={form.window_start}
                                        onChange={(e) => setField('window_start', e.target.value)} disabled={submitting}/>
                                </div>
                                <div>
                                    <span className="urgent-modal__sublabel">Конец</span>
                                    <input className="urgent-modal__input" type="time"
                                        value={form.window_end}
                                        onChange={(e) => setField('window_end', e.target.value)} disabled={submitting}/>
                                </div>
                            </div>
                            {(errors.window_start || errors.window_end) && (
                                <p className="urgent-modal__error">
                                    {errors.window_start || errors.window_end}
                                </p>
                            )}
                        </div>
                    ) : (
                        <div className="urgent-modal__field">
                            <label className="urgent-modal__label">Окно времени</label>
                            <p className="urgent-modal__hint">
                                Сейчас ({nowHHMM()}) — через 2 часа ({plus2hHHMM()})
                            </p>
                        </div>
                    )}
                </form>

                <footer className="urgent-modal__footer">
                    <button type="button" className="urgent-modal__submit"
                            onClick={handleSubmit} disabled={submitting}>
                        {submitting ? 'Геокодирование…' : 'Назначить и перестроить'}
                    </button>
                    <button type="button" className="urgent-modal__cancel"
                            onClick={onClose} disabled={submitting}>
                        {geoState === false ? 'Закрыть' : 'Отмена'}
                    </button>
                </footer>
            </section>
        </main>,
        document.body,
    )
}

export default UrgentRequestModal