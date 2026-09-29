import './UnallocatedCard.css'

const UnallocatedCard = ({
    request,
    isActive,
    mode = 'unallocated',      // 'unallocated' | 'cancelled'
    onSelect,
    onAssignMaster,
    onClientCancel,
    onEditCoords,
    onRestore,
}) => {
    if (!request) return null

    const isCancelled = mode === 'cancelled'
    const noCoords = !request.has_coords && !isCancelled

    const handleClick = () => onSelect?.(request.id)

    return (
        <article
            className={
                'unallocated-card' +
                (isActive ? ' unallocated-card--active' : '') +
                (noCoords ? ' unallocated-card--no-coords' : '') +
                (isCancelled ? ' unallocated-card--cancelled' : '')
            }
            onClick={isCancelled ? undefined : handleClick}
        >
            <header className="unallocated-card__header">
                <div className="unallocated-card__title-row">
                    <h3 className="unallocated-card__title">
                        Заявка #{request.external_id ?? request.id}
                    </h3>
                    {request.request_type && (
                        <span className="unallocated-card__type">
                            {request.request_type}
                        </span>
                    )}
                    {isCancelled && (
                        <span className="unallocated-card__cancelled">
                            Отменена клиентом
                        </span>
                    )}
                </div>
                <div className="unallocated-card__meta">
                    <span className="unallocated-card__date">{request.date}</span>
                    {request.window && (
                        <span className="unallocated-card__window">{request.window}</span>
                    )}
                    {isCancelled && request.cancelled_at && (
                        <span className="unallocated-card__time">
                            в {request.cancelled_at}
                        </span>
                    )}
                </div>
            </header>

            <p className="unallocated-card__address">{request.address}</p>

            {request.service && !isCancelled && (
                <p className="unallocated-card__service">{request.service}</p>
            )}

            {noCoords && (
                <p className="unallocated-card__warn">
                    ⚠ {request.unassigned_reason || 'Не удалось геокодировать адрес'}
                </p>
            )}

            {isCancelled && (
                <div
                    className="unallocated-card__actions"
                    onClick={(e) => e.stopPropagation()}
                >
                    <button
                        type="button"
                        className="unallocated-card__btn unallocated-card__btn--restore"
                        onClick={() => onRestore?.(request)}
                    >
                        ↩ Вернуть в нераспределённые
                    </button>
                </div>
            )}

            {!isCancelled && isActive && (
                <div
                    className="unallocated-card__actions"
                    onClick={(e) => e.stopPropagation()}
                >
                    {noCoords && (
                        <button
                            type="button"
                            className="unallocated-card__btn unallocated-card__btn--coords"
                            onClick={() => onEditCoords?.(request)}
                        >
                            📍 Задать координаты
                        </button>
                    )}
                    <button
                        type="button"
                        className="unallocated-card__btn unallocated-card__btn--assign"
                        onClick={() => onAssignMaster?.(request)}
                    >
                        Назначить мастера
                    </button>
                    <button
                        type="button"
                        className="unallocated-card__btn unallocated-card__btn--cancel"
                        onClick={() => onClientCancel?.(request.id)}
                    >
                        Клиент отменил
                    </button>
                </div>
            )}
        </article>
    )
}

export default UnallocatedCard