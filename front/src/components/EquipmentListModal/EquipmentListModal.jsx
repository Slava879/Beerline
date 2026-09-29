import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import {
    listEquipment,
    patchEquipment,
    deleteEquipment,
} from '../../api/dispatcher'
import './EquipmentListModal.css'

const KIND_LABEL = { router: 'Router', receiver: 'Stb' }

const EquipmentListModal = ({ isOpen, onClose, onChanged, onCreateNew }) => {
    const [items, setItems]     = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError]     = useState(null)

    const load = async () => {
        setLoading(true); setError(null)
        try {
            const d = await listEquipment()
            setItems(d.equipment ?? [])
        } catch (e) { setError(e.message) }
        finally { setLoading(false) }
    }

    useEffect(() => {
        if (isOpen) load()
    }, [isOpen])

    if (!isOpen) return null

    const changeQty = async (item, delta) => {
        if (item.quantity + delta < 0) return
        try {
            const updated = await patchEquipment(item.id, { delta })
            setItems((prev) => prev.map((x) => (x.id === item.id ? updated : x)))
            onChanged?.()
        } catch (e) { setError(e.message) }
    }

    const setQty = async (item, value) => {
        const num = Math.max(0, Number(value) || 0)
        try {
            const updated = await patchEquipment(item.id, { quantity: num })
            setItems((prev) => prev.map((x) => (x.id === item.id ? updated : x)))
            onChanged?.()
        } catch (e) { setError(e.message) }
    }

    const removeItem = async (item) => {
        if (!window.confirm(`Удалить «${item.name}» со склада?`)) return
        try {
            await deleteEquipment(item.id)
            setItems((prev) => prev.filter((x) => x.id !== item.id))
            onChanged?.()
        } catch (e) { setError(e.message) }
    }

    return createPortal(
        <main
            className="eq-list__page"
            style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(15,23,42,0.55)' }}
            onClick={onClose}>
            <section className="eq-list" onClick={(e) => e.stopPropagation()}>
                <header className="eq-list__header">
                    <div className="eq-list__title-wrap">
                        <div className="eq-list__badge">📦</div>
                        <h2 className="eq-list__title">Оборудование на складе</h2>
                    </div>
                    <button type="button" className="eq-list__close"
                        onClick={onClose} aria-label="Закрыть">
                        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                            <path d="M1.08 15.36 0 14.28 6.56 7.68 0 1.08 1.08 0 7.64 6.6 14.16 0l1.08 1.08L8.68 7.68l6.56 6.6-1.08 1.08L7.64 8.8 1.08 15.36Z" fill="#94A3B8"/>
                        </svg>
                    </button>
                </header>

                {error && <div className="eq-list__error">{error}</div>}

                <div className="eq-list__body">
                    {loading && <div className="eq-list__empty">Загрузка…</div>}
                    {!loading && items.length === 0 && (
                        <div className="eq-list__empty">Склад пуст</div>
                    )}

                    {!loading && items.map((it) => (
                        <div key={it.id} className="eq-list__row">
                            <div className="eq-list__info">
                                <div className="eq-list__name">{it.name}</div>
                                <div className="eq-list__meta">
                                    Категория: {KIND_LABEL[it.kind] || it.kind}
                                </div>
                            </div>

                            <div className="eq-list__qty">
                                <button type="button" className="eq-list__qty-btn"
                                    onClick={() => changeQty(it, -1)}
                                    disabled={it.quantity === 0}>−</button>
                                <input
                                    className="eq-list__qty-input"
                                    type="number"
                                    min={0}
                                    value={it.quantity}
                                    onChange={(e) => setQty(it, e.target.value)}
                                />
                                <button type="button" className="eq-list__qty-btn"
                                    onClick={() => changeQty(it, +1)}>+</button>
                            </div>

                            <button type="button" className="eq-list__delete"
                                onClick={() => removeItem(it)}>
                                Удалить
                            </button>
                        </div>
                    ))}
                </div>

                <footer className="eq-list__footer">
                    <button type="button" className="eq-list__add"
                        onClick={() => { onCreateNew?.() }}>
                        + Добавить оборудование
                    </button>
                    <button type="button" className="eq-list__close-btn"
                        onClick={onClose}>
                        Закрыть
                    </button>
                </footer>
            </section>
        </main>,
        document.body,
    )
}

export default EquipmentListModal