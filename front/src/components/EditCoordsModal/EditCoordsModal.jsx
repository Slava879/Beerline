import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import './EditCoordsModal.css'

const EditCoordsModal = ({ isOpen, request, onClose, onSave }) => {
    const [lat, setLat] = useState('')
    const [lon, setLon] = useState('')
    const [busy, setBusy] = useState(false)
    const [err, setErr] = useState(null)

    useEffect(() => {
        if (!isOpen) return
        setLat(request?.lat != null ? String(request.lat) : '')
        setLon(request?.lon != null ? String(request.lon) : '')
        setBusy(false)
        setErr(null)
    }, [isOpen, request?.id, request?.lat, request?.lon])

    if (!isOpen) return null

    const submit = async () => {
        const la = parseFloat(lat.replace(',', '.'))
        const lo = parseFloat(lon.replace(',', '.'))
        if (!Number.isFinite(la) || !Number.isFinite(lo)) {
            setErr('Введите числа, например 55.7558 и 37.6173')
            return
        }
        if (la < -90 || la > 90 || lo < -180 || lo > 180) {
            setErr('Координаты вне допустимого диапазона')
            return
        }
        setBusy(true); setErr(null)
        try {
            await onSave?.(request.id, la, lo)
            onClose?.()
        } catch (e) {
            setErr(e?.message || 'Не удалось сохранить координаты')
        } finally {
            setBusy(false)
        }
    }

    return createPortal(
        <main className="edit-coords__page"
              style={{ position:'fixed', inset:0, zIndex:1100, background:'rgba(15,23,42,0.55)' }}
              onClick={() => !busy && onClose?.()}>
            <section className="edit-coords" onClick={(e) => e.stopPropagation()}>
                <header className="edit-coords__header">
                    <h2 className="edit-coords__title">Координаты заявки</h2>
                    <button type="button" className="edit-coords__close"
                            onClick={() => !busy && onClose?.()}>×</button>
                </header>

                <p className="edit-coords__hint">
                    {request?.address || 'Адрес не указан'}
                </p>

                <div className="edit-coords__grid">
                    <label className="edit-coords__field">
                        <span>Широта (lat)</span>
                        <input value={lat} onChange={(e) => setLat(e.target.value)}
                               placeholder="55.7558" disabled={busy} />
                    </label>
                    <label className="edit-coords__field">
                        <span>Долгота (lon)</span>
                        <input value={lon} onChange={(e) => setLon(e.target.value)}
                               placeholder="37.6173" disabled={busy} />
                    </label>
                </div>

                {err && <p className="edit-coords__error">{err}</p>}

                <div className="edit-coords__help">
                    Подсказка: возьмите координаты из Яндекс.Карт — правый клик по точке → «Что здесь?».
                </div>

                <footer className="edit-coords__footer">
                    <button type="button" className="edit-coords__save"
                            onClick={submit} disabled={busy}>
                        {busy ? 'Сохраняем…' : 'Сохранить'}
                    </button>
                    <button type="button" className="edit-coords__cancel"
                            onClick={() => !busy && onClose?.()}>
                        Отмена
                    </button>
                </footer>
            </section>
        </main>,
        document.body,
    )
}

export default EditCoordsModal