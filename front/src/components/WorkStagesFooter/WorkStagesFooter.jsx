import { useState } from 'react'
import cn from 'classnames'

const STAGES = [
    { key: 'take',  title: '1. Взять заявку',  doneText: 'Выполнено (09:40)' },
    { key: 'start', title: '2. Начать работу', doneText: 'Нажмите на адресе' },
    { key: 'stop',  title: '3. Завершить',     doneText: 'Завершить (10:40)' },
]

// 🔌 БЭКЕНД: компонент сейчас полностью самодостаточный — этап хранится только тут
// в useState и никуда не сообщается. Чтобы подключить updateRequestStage(requestId, stage)
// и cancelRequestByClient(requestId) из '../../api/engineer', понадобится:
// 1. добавить пропсы requestId и (по желанию) onStageChange
// 2. в onClick у кнопок этапов и у "Клиент отменил заявку" вызывать соответствующую функцию API
// Пока используется в EngineerPage.jsx без этих пропсов — но чтобы менять этап нужной заявки
// (а не просто локальной кнопки), пропсы обязательно понадобятся.
const WorkStagesFooter = () => {
    const [stage, setStage] = useState('take')

    return (
        <div className="menu__footer">
            <div className="menu__container">
                <h2 className="menu__footer-title">ЭТАПЫ ВЫПОЛНЕНИЯ РАБОТЫ:</h2>
                <div className="menu__footer-buttons-stages">
                    {STAGES.map((s) => (
                        <button key={s.key}
                            className={cn('menu__footer-button', `menu__footer-button-${s.key}`,
                                { 'menu__footer-button--current': stage === s.key })}
                            onClick={() => setStage(s.key)}>
                            <p className="button__title">{s.title}</p>
                            <p className="button__description">{s.doneText}</p>
                        </button>
                    ))}
                </div>
                <button className="menu__footer-button-revoke">Клиент отменил заявку</button>
            </div>
        </div>
    )
}

export default WorkStagesFooter