// frontend/src/pages/DispatcherPage/DistributedCard.jsx
import InfoButton from '../../components/InfoButton/InfoButton'
import RequestStagesFooter from './RequestStagesFooter'

const STATUS_CLASS = {
    NEW:         'status--new',
    TAKEN:       'status--taken',
    IN_PROGRESS: 'status--progress',
    DONE:        'status--done',
    CANCELLED:   'status--cancelled',
}
const statusClassOf = (s) =>
    STATUS_CLASS[String(s || 'NEW').toUpperCase()] || 'status--new'

const DistributedCard = ({
    request,
    engineerName,
    seq,
    isActive,
    busy,
    cardRef,
    onSelect,
    onChangeStatus,
    onCancelRequest,
    onChangeMaster,
}) => {
    const handleClick = () => {
        if (!isActive) onSelect?.(request.id)
    }

    return (
        <article
            ref={cardRef}
            className={
                'menu__distributed-card' +
                (isActive ? ' menu__distributed-card--active' : '')
            }
            onClick={handleClick}
        >
            <div className="menu__distributed-card-row">
                <div className="menu__distributed-card-info">
                    <h3 className="menu__distributed-card-title">
                        {seq != null && (
                            <span className="menu__distributed-card-seq">#{seq}</span>
                        )}{' '}
                        Заявка #{request.external_id ?? request.id}{' '}
                        {request.request_type && (
                            <span className="menu__distributed-card-type">
                                {request.request_type}
                            </span>
                        )}
                        {request.assignment_reason && (
                            <InfoButton
                                title="Почему назначена этому мастеру"
                                align="left"
                            >
                                {request.assignment_reason}
                            </InfoButton>
                        )}
                    </h3>
                    <p className="menu__distributed-card-description">
                        {request.description}
                    </p>
                    <p className="menu__distributed-card-master">
                        <span className="menu__distributed-card-master-label">
                            Мастер:
                        </span>{' '}
                        {engineerName ? (
                            <span className="menu__distributed-card-master-name">
                                {engineerName}
                            </span>
                        ) : (
                            <span className="menu__distributed-card-master-empty">
                                не назначен
                            </span>
                        )}
                    </p>
                </div>
                <div className="menu__distributed-card-right">
                    <p
                        className={
                            'menu__distributed-card-status ' +
                            statusClassOf(request.status)
                        }
                    >
                        {request.status}
                    </p>
                </div>
            </div>

            {isActive && (
                <div
                    className="menu__distributed-card-stages"
                    onClick={(e) => e.stopPropagation()}
                >
                    <RequestStagesFooter
                        request={request}
                        busy={busy}
                        onChangeStatus={onChangeStatus}
                        onCancelRequest={onCancelRequest}
                        onChangeMaster={(req) =>
                            onChangeMaster?.({
                                id: req.id,
                                address: req.description,
                                service: 'Сменить мастера',
                                reason: 'Ручная смена мастера',
                            })
                        }
                    />
                </div>
            )}
        </article>
    )
}

export default DistributedCard