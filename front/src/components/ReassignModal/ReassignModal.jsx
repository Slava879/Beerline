import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { getSuitableEngineers } from '../../api/dispatcher'
import './ReassignModal.css'

const TRANSPORT_ICON = {
    'автомобиль': '🚗',
    'велосипед':  '🚲',
    'пешеход':    '🚶',
}

const CandidateCard = ({ item, onPick, busy }) => {
    const isFree = item.is_free
    const hasWait = item.has_wait_window

    const badge = isFree
        ? { cls: 'cand__badge--free', text: '🟢 Свободен' }
        : hasWait
            ? { cls: 'cand__badge--wait', text: '🟡 Есть окно' }
            : { cls: 'cand__badge--busy', text: '⚪ Остальные' }

    const shifts = item.shifts || []

    return (
        <article className="cand">
            <header className="cand__head">
                <div className="cand__title">
                    <span className={`cand__badge ${badge.cls}`}>{badge.text}</span>
                    <span className="cand__name">
                        {TRANSPORT_ICON[item.engineer.transport] || '👤'}{' '}
                        {item.engineer.name}
                    </span>
                </div>
                <div className="cand__cost">
                    +{item.added_cost.toFixed(0)} к стоимости
                </div>
            </header>

            <div className="cand__meta">
                <span>Смена {item.engineer.shift_start}–{item.engineer.shift_end}</span>
                <span>Заявок: {item.current_load}</span>
                <span>Финиш: {item.schedule_end}</span>
                <span>Пробег: {item.total_km} км</span>
            </div>

            {!isFree && (
                <div className="cand__insert">
                    {item.between_before && item.between_after ? (
                        <>Вставится между&nbsp;
                            <b>#{item.between_before.id}</b> (до {item.between_before.end}) и&nbsp;
                            <b>#{item.between_after.id}</b> (с {item.between_after.start})
                        </>
                    ) : item.between_before ? (
                        <>Вставится после <b>#{item.between_before.id}</b> (до {item.between_before.end})</>
                    ) : item.between_after ? (
                        <>Вставится до <b>#{item.between_after.id}</b> (с {item.between_after.start})</>
                    ) : null}
                    {typeof item.travel_min === 'number' && (
                        <> · доехать ~<b>{item.travel_min} мин</b></>
                    )}
                </div>
            )}

            {isFree && typeof item.travel_min === 'number' && (
                <div className="cand__insert">
                    Доехать до заявки ~<b>{item.travel_min} мин</b>
                </div>
            )}

            {hasWait && item.wait_window && (
                <div className="cand__wait">⏳ Окно ожидания: {item.wait_window}</div>
            )}

            {shifts.length > 0 && (
                <div className="cand__shifts">
                    <div className="cand__shifts-title">
                        Последующие заявки сдвинутся:
                    </div>
                    <ul className="cand__shifts-list">
                        {shifts.map((s) => (
                            <li key={s.id}>
                                <b>#{s.id}</b>{' '}
                                <span className="cand__shift-old">
                                    {s.old_start}–{s.old_end}
                                </span>
                                {' → '}
                                <span className="cand__shift-new">
                                    {s.new_start}–{s.new_end}
                                </span>{' '}
                                <span className={
                                    s.delta_min > 0
                                        ? 'cand__shift-delta cand__shift-delta--plus'
                                        : 'cand__shift-delta cand__shift-delta--minus'
                                }>
                                    ({s.delta_min > 0 ? '+' : ''}{s.delta_min} мин)
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            <div className="cand__skills">
                {item.engineer.skills.map((s) => (
                    <span key={s} className="cand__skill">{s}</span>
                ))}
            </div>

            <button
                type="button"
                className="cand__pick"
                disabled={busy}
                onClick={() => onPick(item.engineer.id)}
            >
                Назначить
            </button>
        </article>
    )
}

const ReassignModal = ({ isOpen, request, districtId, visitDate, onClose, onAssign }) => {
    const [loading, setLoading] = useState(false)
    const [error,   setError]   = useState(null)
    const [data,    setData]    = useState(null)
    const [busyId,  setBusyId]  = useState(null)

    useEffect(() => {
        if (!isOpen || !request?.id || !districtId) return
        setLoading(true)
        setError(null)
        setData(null)
        getSuitableEngineers(request.id, districtId, visitDate)
            .then((res) => setData(res))
            .catch((e) => setError(e?.message || 'Не удалось получить список'))
            .finally(() => setLoading(false))
    }, [isOpen, request?.id, districtId, visitDate])

    if (!isOpen) return null

    const handlePick = async (engineerId) => {
        setBusyId(engineerId)
        try {
            await onAssign?.(request.id, engineerId)
            onClose?.()
        } catch (e) {
            setError(e?.message || 'Не удалось назначить')
        } finally {
            setBusyId(null)
        }
    }

    const suitable  = data?.suitable ?? []
    const freeList  = suitable.filter((s) => s.is_free)
    const waitList  = suitable.filter((s) => !s.is_free && s.has_wait_window)
    const otherList = suitable.filter((s) => !s.is_free && !s.has_wait_window)

    return createPortal(
        <main className="reassign__page"
              style={{ position: 'fixed', inset: 0, zIndex: 1100,
                       background: 'rgba(15,23,42,0.55)' }}
              onClick={() => !busyId && onClose?.()}>
            <section className="reassign" onClick={(e) => e.stopPropagation()}>
                <header className="reassign__header">
                    <div>
                        <h2 className="reassign__title">Выбор мастера</h2>
                        {request?.address && (
                            <p className="reassign__subtitle">{request.address}</p>
                        )}
                        {data?.order?.window && (
                            <p className="reassign__subtitle">
                                Окно: {data.order.window} · Тип: {data.order.bk_type}
                            </p>
                        )}
                    </div>
                    <button type="button" className="reassign__close"
                            onClick={() => !busyId && onClose?.()}>×</button>
                </header>

                {loading && <p className="reassign__hint">Подбираем мастеров…</p>}
                {error && <p className="reassign__error">{error}</p>}

                {!loading && !error && suitable.length === 0 && (
                    <div className="reassign__empty">
                        Нет мастеров, которым можно назначить эту заявку.
                        Проверьте навыки и оборудование у сотрудников.
                    </div>
                )}

                {!loading && suitable.length > 0 && (
                    <div className="reassign__body">
                        {freeList.length > 0 && (
                            <>
                                <h3 className="reassign__group">
                                    🟢 Свободные мастера ({freeList.length})
                                </h3>
                                {freeList.map((it) => (
                                    <CandidateCard key={it.engineer.id} item={it}
                                                   onPick={handlePick} busy={!!busyId} />
                                ))}
                            </>
                        )}

                        {waitList.length > 0 && (
                            <>
                                <h3 className="reassign__group">
                                    🟡 Мастера с окном ожидания ({waitList.length})
                                </h3>
                                {waitList.map((it) => (
                                    <CandidateCard key={it.engineer.id} item={it}
                                                   onPick={handlePick} busy={!!busyId} />
                                ))}
                            </>
                        )}

                        {otherList.length > 0 && (
                            <>
                                <h3 className="reassign__group">
                                    ⚪ Успевают, но без большого окна ({otherList.length})
                                </h3>
                                {otherList.map((it) => (
                                    <CandidateCard key={it.engineer.id} item={it}
                                                   onPick={handlePick} busy={!!busyId} />
                                ))}
                            </>
                        )}
                    </div>
                )}

                <footer className="reassign__footer">
                    <button type="button" className="reassign__cancel"
                            onClick={() => !busyId && onClose?.()}>
                        Отмена
                    </button>
                </footer>
            </section>
        </main>,
        document.body,
    )
}

export default ReassignModal