const ReplanningEventCard = ({ event, onReschedule, onDetails }) => (
    <div className="menu__event-card">
        <div className="menu__event-card-header">
            <div className="menu__event-card-title">{event.title}</div>
            <div className="menu__event-card-time">{event.time}</div>
        </div>
        <div className="menu__event-card-description">{event.description}</div>
        <div className="menu__event-card-reason">{event.reason}</div>
        <div className="menu__event-card-buttons">
            <button className="menu__event-card-button menu__event-card-button--reschedule"
                onClick={() => onReschedule(event)}>
                Перепланировать
            </button>
            <button className="menu__event-card-button menu__event-card-button--details"
                onClick={() => onDetails(event)}>
                Детали ›
            </button>
        </div>
    </div>
)

export default ReplanningEventCard