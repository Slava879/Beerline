import { useState } from 'react'
import PageHeader from '../../components/PageHeader/PageHeader'
import WorkStagesFooter from '../../components/WorkStagesFooter/WorkStagesFooter'
import { openRequest, queuedRequests } from './mockData'
// 🔌 БЭКЕНД (когда будет готов): заменить импорт выше на getEngineerRequests()
// из '../../api/engineer' — она возвращает { openRequest, queuedRequests } одним запросом.
// Вызывать в useEffect при монтировании страницы, класть в useState (см. пример
// такого паттерна в DispatcherPage.jsx после того, как он будет переведён на API).

// Страница инженера: одна активная заявка всегда развёрнута (openRequest),
// остальные — свёрнутый список, раскрывается по кнопке "Показать все заявки".
// Каждую карточку можно раскрыть/свернуть кликом отдельно (expandedIds).
const EngineerPage = () => {
    const [showAll, setShowAll] = useState(false)
    const [expandedIds, setExpandedIds] = useState([])

    const toggleCard = (id) => {
        setExpandedIds((prev) =>
            prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
        )
    }

    const renderExpanded = (r) => (
        <>
            <h3 className="menu__open-card-title">Заявка #{r.id}</h3>
            <p className="menu__open-card-data">
                Дата визита: <span className="menu__open-card-data-accent">{r.date}</span>
            </p>
            <p className="menu__open-card-time">
                Окно: <span className="menu__open-card-time-accent">{r.window}</span>
                {' '} | Адрес: {r.address}
            </p>
            <p className="menu__open-card-service">Услуга: {r.service}</p>
            <h4 className="menu__open-card-equipments-title">НЕОБХОДИМОЕ ОБОРУДОВАНИЕ:</h4>
            <div className="menu__open-card-equipments">
                {r.equipments.map((eq, i) => (
                    <div key={i} className="menu__open-card-equipment">
                        <p className="menu__open-card-equipment-title">{eq.title}</p>
                        <p className="menu__open-card-equipment-quantity">{eq.qty}</p>
                    </div>
                ))}
            </div>
        </>
    )

    const renderCollapsed = (r) => (
        <>
            <div className="menu__close-card-info">
                <h3 className="menu__close-card-title">Заявка #{r.id}</h3>
                <p className="menu__close-card-description">
                    {r.description || `${r.date} (${r.window}) | ${r.address}`}
                </p>
            </div>
            {r.status && <p className="menu__close-card-status">{r.status}</p>}
        </>
    )

    const renderCard = (r) => (
        <article key={r.id}
            className={expandedIds.includes(r.id) ? 'menu__open-card' : 'menu__close-card'}
            onClick={() => toggleCard(r.id)}
            style={{ cursor: 'pointer' }}>
            {expandedIds.includes(r.id) ? renderExpanded(r) : renderCollapsed(r)}
        </article>
    )

    return (
        <main className="main">
            <section className="section menu__section">
                <div className="menu__container">
                    <PageHeader />
                    <main className="menu__main">
                        <div className="menu__container">
                            <div className="menu__applications">
                                <div className="menu__applications-info">
                                    <h2 className="menu__applications-title">ВХОДЯЩИЕ ЗАЯВКИ ИЗ АППЛЕТА</h2>
                                    <button className="menu__applications-button" onClick={() => setShowAll(!showAll)}>
                                        {showAll ? 'Скрыть заявки' : 'Показать все заявки'}
                                    </button>
                                </div>

                                <div className="menu__applications-cards">
                                    {/* Активная заявка — всегда на виду, по клику раскрывается */}
                                    {renderCard(openRequest)}

                                    {/* Остальные заявки — по кнопке "Показать все заявки".
                                        Можно раскрыть несколько одновременно, по умолчанию все закрыты */}
                                    {showAll && queuedRequests.map(renderCard)}
                                </div>
                            </div>

                            <WorkStagesFooter />
                        </div>
                    </main>
                </div>
            </section>
        </main>
    )
}

export default EngineerPage
