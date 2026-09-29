import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import './EquipmentFormModal.css'

const KINDS = [
    { value: 'router',   label: 'Router (роутер)' },
    { value: 'receiver', label: 'Stb (приставка)' },
]

const KIND_LABEL = { router: 'Router', receiver: 'Stb' }

const EMPTY = {
    kind: 'router',
    name: 'Router',
    quantity: 0,
}

const EquipmentFormModal = ({ isOpen, onClose, onSubmit }) => {
    const [form, setForm] = useState(EMPTY)
    const [errors, setErrors] = useState({})

    useEffect(() => {
        if (isOpen) { setForm(EMPTY); setErrors({}) }
    }, [isOpen])

    if (!isOpen) return null

    const setField = (name, value) => {
        setForm((prev) => ({ ...prev, [name]: value }))
        if (errors[name]) setErrors((prev) => ({ ...prev, [name]: undefined }))
    }

    const setKind = (value) => {
        // авто-подставляем название по умолчанию, но позволяем изменить
        setForm((prev) => ({
            ...prev,
            kind: value,
            name: prev.name === 'Router' || prev.name === 'Stb' || !prev.name
                ? (KIND_LABEL[value] || prev.name)
                : prev.name,
        }))
    }

    const validate = () => {
        const e = {}
        if (!form.name.trim()) e.name = 'Укажите название'
        if (form.quantity < 0)  e.quantity = 'Количество не может быть отрицательным'
        setErrors(e)
        return Object.keys(e).length === 0
    }

    const handleSubmit = (ev) => {
        ev.preventDefault()
        if (!validate()) return
        onSubmit?.({
            kind: form.kind,
            name: form.name.trim(),
            quantity: Number(form.quantity) || 0,
        })
    }

    return createPortal(
        <main
            className="equip-modal__page"
            style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(15,23,42,0.55)' }}
            onClick={onClose}>
            <section className="equip-modal" onClick={(e) => e.stopPropagation()}>
                <header className="equip-modal__header">
                    <div className="equip-modal__title-wrap">
                        <div className="equip-modal__badge">📦</div>
                        <h2 className="equip-modal__title">Добавить оборудование</h2>
                    </div>
                    <button type="button" className="equip-modal__close"
                        onClick={onClose} aria-label="Закрыть">
                        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                            <path d="M1.08 15.36 0 14.28 6.56 7.68 0 1.08 1.08 0 7.64 6.6 14.16 0l1.08 1.08L8.68 7.68l6.56 6.6-1.08 1.08L7.64 8.8 1.08 15.36Z" fill="#94A3B8"/>
                        </svg>
                    </button>
                </header>

                <form className="equip-modal__body" onSubmit={handleSubmit}>
                    <div className="equip-modal__field">
                        <label className="equip-modal__label">Категория</label>
                        <select className="equip-modal__input"
                            value={form.kind}
                            onChange={(e) => setKind(e.target.value)}>
                            {KINDS.map((k) => (
                                <option key={k.value} value={k.value}>{k.label}</option>
                            ))}
                        </select>
                    </div>

                    <div className="equip-modal__field">
                        <label className="equip-modal__label">Название *</label>
                        <input className="equip-modal__input" type="text"
                            value={form.name}
                            onChange={(e) => setField('name', e.target.value)}
                            placeholder="Например: Router" />
                        {errors.name && <p className="equip-modal__error">{errors.name}</p>}
                    </div>

                    <div className="equip-modal__field">
                        <label className="equip-modal__label">Количество на складе</label>
                        <input className="equip-modal__input" type="number" min={0}
                            value={form.quantity}
                            onChange={(e) => setField('quantity', e.target.value)} />
                        {errors.quantity && <p className="equip-modal__error">{errors.quantity}</p>}
                    </div>
                </form>

                <footer className="equip-modal__footer">
                    <button type="button" className="equip-modal__submit" onClick={handleSubmit}>
                        Добавить
                    </button>
                    <button type="button" className="equip-modal__cancel" onClick={onClose}>
                        Отмена
                    </button>
                </footer>
            </section>
        </main>,
        document.body,
    )
}

export default EquipmentFormModal