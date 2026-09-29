import { useEffect } from 'react'

const AUTO_CLOSE_MS = { urgent: 25000, normal: 12000 }

// Тосты входящих заявок из апплета (правый верхний угол на странице диспетчера).
// Сейчас toasts приходят из DispatcherPage.jsx, где они генерируются рандомом
// (см. комментарий в DispatcherPage.jsx про WebSocket) — сам этот компонент от
// источника данных не зависит и трогать его для интеграции с бэкендом не нужно,
// он просто рисует то, что ему передали, и сам себя закрывает по таймеру.
const IncomingRequestToast = ({ toasts, onAccept, onDismiss }) => {
    useEffect(() => {
        const timers = toasts.map((t) =>
            setTimeout(() => onDismiss(t.id), AUTO_CLOSE_MS[t.priority] ?? 12000)
        )
        return () => timers.forEach(clearTimeout)
    }, [toasts, onDismiss])

    return (
        <div className="incoming">
            {toasts.map((t) => (
                <div key={t.id} className={`incoming__toast incoming__toast--${t.priority}`}>
                    <div className="incoming__header">
                        <p className="incoming__title">
                            {t.priority === 'urgent' ? '⚠ Срочная заявка' : 'Новая заявка'} #{t.id}
                        </p>
                        <button className="incoming__close" onClick={() => onDismiss(t.id)} aria-label="Закрыть">
                            ×
                        </button>
                    </div>
                    <p className="incoming__row">Адрес: {t.address}</p>
                    <p className="incoming__row">Услуга: {t.service}</p>
                    <div className="incoming__footer">
                        <p className="incoming__time">Окно: {t.window}</p>
                        <button className="incoming__accept" onClick={() => onAccept(t.id)}>
                            Принять
                        </button>
                    </div>
                </div>
            ))}
        </div>
    )
}

export default IncomingRequestToast
