import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import './EngineerFormModal.css'

// Навыки = те же типы работ, что и в заявках
const WORK_TYPES = [
    { value: 'connection', label: 'Подключение' },
    { value: 'local',      label: 'Локальная заявка' },
    { value: 'reorder',    label: 'Дозаказ' },
    { value: 'global',     label: 'Глобальная проблема' },
]

const TRANSPORT_OPTIONS = [
    { value: 'Пеший',      label: 'Пеший' },
    { value: 'Велосипед',  label: 'Велосипед' },
    { value: 'Автомобиль', label: 'Автомобиль' },
]

const EMPTY = {
    fio: '',
    birth_date: '',
    phone: '',
    transport: 'Пеший',
    shift_start: '08:00',
    shift_end: '17:00',
    skills: [],               // список value из WORK_TYPES
}

const EngineerFormModal = ({ isOpen, onClose, onSubmit, districtId }) => {
    const [form, setForm] = useState(EMPTY)
    const [errors, setErrors] = useState({})

    useEffect(() => {
        if (isOpen) {
            setForm(EMPTY)
            setErrors({})
        }
    }, [isOpen])

    if (!isOpen) return null

    const setField = (name, value) => {
        setForm((prev) => ({ ...prev, [name]: value }))
        if (errors[name]) setErrors((prev) => ({ ...prev, [name]: undefined }))
    }

    const toggleSkill = (value) => {
        setForm((prev) => {
            const has = prev.skills.includes(value)
            return {
                ...prev,
                skills: has
                    ? prev.skills.filter((s) => s !== value)
                    : [...prev.skills, value],
            }
        })
        if (errors.skills) setErrors((prev) => ({ ...prev, skills: undefined }))
    }

    const validate = () => {
        const e = {}
        if (!form.fio.trim()) e.fio = 'Укажите ФИО'
        if (!form.shift_start) e.shift_start = 'Укажите начало смены'
        if (!form.shift_end)   e.shift_end = 'Укажите конец смены'
        if (form.shift_start && form.shift_end && form.shift_start >= form.shift_end) {
            e.shift_end = 'Конец смены должен быть позже начала'
        }
        setErrors(e)
        return Object.keys(e).length === 0
    }

    const handleSubmit = (ev) => {
        ev.preventDefault()
        if (!validate()) return

        // превращаем value в человекочитаемые labels — так же, как в UrgentRequestModal
        const skillLabels = form.skills
            .map((v) => WORK_TYPES.find((t) => t.value === v)?.label)
            .filter(Boolean)

        onSubmit?.({
            district_id: districtId,
            fio: form.fio.trim(),
            birth_date: form.birth_date || null,
            phone: form.phone.trim() || null,
            transport: form.transport,
            shift_start: form.shift_start,
            shift_end: form.shift_end,
            skills: skillLabels,
        })
    }

    return createPortal(
        <main
            className="engineer-modal__page"
            style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(15,23,42,0.55)' }}
            onClick={onClose}>
            <section className="engineer-modal" onClick={(e) => e.stopPropagation()}>
                <header className="engineer-modal__header">
                    <div className="engineer-modal__title-wrap">
                        <div className="engineer-modal__badge">🧑‍🔧</div>
                        <h2 className="engineer-modal__title">Создание Инженера</h2>
                    </div>
                    <button
                        type="button"
                        className="engineer-modal__close"
                        onClick={onClose}
                        aria-label="Закрыть">
                        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                            <path d="M1.08 15.36 0 14.28 6.56 7.68 0 1.08 1.08 0 7.64 6.6 14.16 0l1.08 1.08L8.68 7.68l6.56 6.6-1.08 1.08L7.64 8.8 1.08 15.36Z" fill="#94A3B8"/>
                        </svg>
                    </button>
                </header>

                <form className="engineer-modal__body" onSubmit={handleSubmit}>
                    {/* ФИО */}
                    <div className="engineer-modal__field">
                        <label className="engineer-modal__label">ФИО *</label>
                        <input
                            className="engineer-modal__input"
                            type="text"
                            value={form.fio}
                            onChange={(e) => setField('fio', e.target.value)}
                            placeholder="Иванов Иван Иванович"
                        />
                        {errors.fio && <p className="engineer-modal__error">{errors.fio}</p>}
                    </div>

                    {/* Дата рождения + телефон */}
                    <div className="engineer-modal__row">
                        <div className="engineer-modal__field">
                            <label className="engineer-modal__label">Дата рождения</label>
                            <input
                                className="engineer-modal__input"
                                type="date"
                                value={form.birth_date}
                                onChange={(e) => setField('birth_date', e.target.value)}
                            />
                        </div>
                        <div className="engineer-modal__field">
                            <label className="engineer-modal__label">Номер телефона</label>
                            <input
                                className="engineer-modal__input"
                                type="tel"
                                value={form.phone}
                                onChange={(e) => setField('phone', e.target.value)}
                                placeholder="+7 (___) ___-__-__"
                            />
                        </div>
                    </div>

                    {/* Транспорт */}
                    <div className="engineer-modal__field">
                        <label className="engineer-modal__label">Транспорт</label>
                        <select
                            className="engineer-modal__input engineer-modal__select"
                            value={form.transport}
                            onChange={(e) => setField('transport', e.target.value)}>
                            {TRANSPORT_OPTIONS.map((t) => (
                                <option key={t.value} value={t.value}>{t.label}</option>
                            ))}
                        </select>
                    </div>

                    {/* Рабочая смена */}
                    <div className="engineer-modal__row">
                        <div className="engineer-modal__field">
                            <label className="engineer-modal__label">Начало смены *</label>
                            <input
                                className="engineer-modal__input"
                                type="time"
                                value={form.shift_start}
                                onChange={(e) => setField('shift_start', e.target.value)}
                            />
                            {errors.shift_start && (
                                <p className="engineer-modal__error">{errors.shift_start}</p>
                            )}
                        </div>
                        <div className="engineer-modal__field">
                            <label className="engineer-modal__label">Конец смены *</label>
                            <input
                                className="engineer-modal__input"
                                type="time"
                                value={form.shift_end}
                                onChange={(e) => setField('shift_end', e.target.value)}
                            />
                            {errors.shift_end && (
                                <p className="engineer-modal__error">{errors.shift_end}</p>
                            )}
                        </div>
                    </div>

                    {/* Навыки: мультивыбор */}
                    <div className="engineer-modal__field">
                        <label className="engineer-modal__label">
                            Навыки <span className="engineer-modal__hint">(можно выбрать несколько)</span>
                        </label>
                        <div className="engineer-modal__skills">
                            {WORK_TYPES.map((t) => {
                                const active = form.skills.includes(t.value)
                                return (
                                    <button
                                        key={t.value}
                                        type="button"
                                        className={
                                            'engineer-modal__skill' +
                                            (active ? ' engineer-modal__skill--active' : '')
                                        }
                                        onClick={() => toggleSkill(t.value)}>
                                        {t.label}
                                    </button>
                                )
                            })}
                        </div>
                    </div>
                </form>

                <footer className="engineer-modal__footer">
                    <button
                        type="button"
                        className="engineer-modal__submit"
                        onClick={handleSubmit}>
                        Создать Мастера
                    </button>
                    <button
                        type="button"
                        className="engineer-modal__cancel"
                        onClick={onClose}>
                        Отмена
                    </button>
                </footer>
            </section>
        </main>,
        document.body,
    )
}

export default EngineerFormModal