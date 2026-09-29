import './SidebarLayout.css'

// Общий каркас "контент слева + карта справа" для страниц с картой.
// Сама карта (layout__map) сейчас пустой div — интеграция карты (Яндекс/Google/Leaflet)
// не в этом компоненте, а отдельная задача.
const SidebarLayout = ({ children }) => {
    return (
        <div className="layout">
            <section className="menu__section">
                <div className="menu__container">
                    {children}
                </div>
            </section>
            <div className="layout__map"></div>
        </div>
    )
}

export default SidebarLayout