import './RequestStagesFooter.css'

const STAGES = [
    { key: 'taken',       num: 1, title: 'Мастер выехал' },
    { key: 'in_progress', num: 2, title: 'Начал работу'  },
    { key: 'done',        num: 3, title: 'Завершил'      },
]

// Пройденные этапы для каждого статуса (ключи — lowercase, как RequestStatus.value)
const DONE_STAGES = {
    new:         [],
    taken:       ['taken'],
    in_progress: ['taken', 'in_progress'],
    done:        ['taken', 'in_progress', 'done'],
    cancelled:   ['taken', 'in_progress'],
}

// Какое значение отправляем на бэк при клике
const STAGE_ACTION = {
    taken:       'taken',
    in_progress: 'in_progress',
    done:        'done',
}

const RequestStagesFooter = ({
    request,
    busy = false,
    onChangeStatus,
    onCancelRequest,
    onChangeMaster,
}) => {
    const status = String(request?.status ?? 'new').toLowerCase()
    const doneStages = DONE_STAGES[status] ?? []
    const isCancelled = status === 'cancelled'
    const isFinished = status === 'done' || isCancelled

    const currentKey = STAGES.find((s) => !doneStages.includes(s.key))?.key

    const handleStageClick = (stageKey) => {
        if (busy) return
        if (!onChangeStatus) return
        const nextStatus = STAGE_ACTION[stageKey]
        if (!nextStatus) return
        onChangeStatus(request.id, nextStatus)
    }

    return (
        <div className="stages-footer">
            <div className="stages-footer__stages">
                {STAGES.map((stage) => {
                    const isDone = doneStages.includes(stage.key)
                    const isCurrent = stage.key === currentKey && !isFinished
                    const isFuture = !isDone && !isCurrent

                    const isClickable = isCurrent && !busy

                    const stateClass = isDone
                        ? 'stages-footer__stage--done'
                        : isCurrent
                            ? 'stages-footer__stage--current'
                            : 'stages-footer__stage--future'

                    const hint = isDone
                        ? '✓ Выполнено'
                        : isCurrent
                            ? 'Ожидает'
                            : '—'

                    return (
                        <button
                            key={stage.key}
                            type="button"
                            className={`stages-footer__stage ${stateClass}`}
                            disabled={!isClickable}
                            onClick={() => handleStageClick(stage.key)}
                        >
                            <span className="stages-footer__stage-label">
                                {stage.num}. {stage.title}
                            </span>
                            <span className="stages-footer__stage-hint">
                                {hint}
                            </span>
                        </button>
                    )
                })}
            </div>

            <div className="stages-footer__actions">
                <button
                    type="button"
                    className="stages-footer__action stages-footer__action--ghost"
                    onClick={() => !busy && onChangeMaster?.(request)}
                    disabled={busy}
                >
                    Изменить мастера
                </button>

                <button
                    type="button"
                    className="stages-footer__action stages-footer__action--cancel"
                    onClick={() => !busy && !isFinished && onCancelRequest?.(request.id)}
                    disabled={busy || isFinished}
                >
                    Клиент отменил заявку
                </button>
            </div>
        </div>
    )
}

export default RequestStagesFooter