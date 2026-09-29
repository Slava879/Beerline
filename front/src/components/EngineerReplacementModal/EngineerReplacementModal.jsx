import { useState } from 'react'
import { createPortal } from 'react-dom'
import { replacementCandidates } from './mockData'
// 🔌 БЭКЕНД: replacementCandidates сейчас мок. Заменить на getReplacementCandidates(request.id)
// из '../../api/candidates' — это отдельный useState + useEffect(fetch по request.id, когда
// модалка открылась). ВАЖНО: цвета/бейджи (dot, nameColor, skillTag.bg и т.п. в моке) фронт
// вычисляет сам из available/recommended — бэкенд их присылать не должен, см. комментарий
// в src/api/candidates.js.

// Модалка замены/назначения мастера на конкретную заявку: поиск по имени/навыкам,
// фильтр-чипы (рекомендуемые/на авто/ТМЦ в наличии) и список кандидатов.
const CHIPS = [
    { key: 'recommended', cls: 'assign-master-chip assign-master-chip-recommended', label: '⭐ Рекомендуемые' },
    { key: 'car', cls: 'assign-master-chip assign-master-chip-car', label: '🚗 На авто' },
    { key: 'stock', cls: 'assign-master-chip assign-master-chip-stock', label: '📦 ТМЦ в наличии' },
]

const EngineerReplacementModal = ({ isOpen, request, onClose, onAssign }) => {
    const [query, setQuery] = useState('')
    const [activeChips, setActiveChips] = useState([])

    if (!isOpen || !request) return null

    const filtered = replacementCandidates.filter((c) =>
        c.name.toLowerCase().includes(query.toLowerCase()) ||
        c.details.some((d) => d.text.toLowerCase().includes(query.toLowerCase()))
    )

    return createPortal(
        <div style={{
            position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(15,23,42,0.55)',
            display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '20px',
            overflowY: 'auto',
        }}>
            <div className="assign-master-modal">
                <div className="assign-master-header">
                    <div className="assign-master-header-titles">
                        <h2 className="assign-master-title">Назначение мастера на заявку #{request.id}</h2>
                        <p className="assign-master-subtitle">
                            Адрес: ул. {request.address} • Услуга: {request.service}
                        </p>
                    </div>
                    <button className="assign-master-close-btn" onClick={onClose}>&times;</button>
                </div>

                <div className="assign-master-search-wrapper">
                    <input type="text" className="assign-master-search-input"
                        placeholder="Поиск по имени, авто или навыкам..."
                        value={query} onChange={(e) => setQuery(e.target.value)} />
                </div>

                <div className="assign-master-filters">
                    {CHIPS.map((chip) => (
                        <div key={chip.key} className={chip.cls}
                            style={activeChips.includes(chip.key) ? { outline: '2px solid #27272A' } : { opacity: 0.75 }}
                            onClick={() => setActiveChips((prev) =>
                                prev.includes(chip.key) ? prev.filter((k) => k !== chip.key) : [...prev, chip.key])}>
                            {chip.label}
                        </div>
                    ))}
                </div>

                <div className="assign-master-list-label">Доступные инженеры ({filtered.length})</div>

                <div className="assign-master-list">
                    {filtered.map((c) => (
                        <div key={c.id} className={c.recommended ? 'assign-master-card-ivan'
                            : c.available ? 'assign-master-card-alexey' : 'assign-master-card-dmitry'}>
                            <div className={`assign-master-card-${c.recommended ? 'ivan' : c.available ? 'alexey' : 'dmitry'}-left`}>
                                <div className={`assign-master-card-${c.recommended ? 'ivan' : c.available ? 'alexey' : 'dmitry'}-name-group`}>
                                    <div className={`assign-master-card-${c.recommended ? 'ivan' : c.available ? 'alexey' : 'dmitry'}-dot`}
                                        style={{ backgroundColor: c.dot }}></div>
                                    <div className={`assign-master-card-${c.recommended ? 'ivan' : c.available ? 'alexey' : 'dmitry'}-name`}
                                        style={{ color: c.nameColor }}>
                                        {c.name}
                                    </div>
                                    {c.recommended && (
                                        <div className="assign-master-card-ivan-badge">Оптимален AI</div>
                                    )}
                                </div>

                                {c.details.map((d, i) => (
                                    <div key={i}
                                        className={`assign-master-card-${c.recommended ? 'ivan' : c.available ? 'alexey' : 'dmitry'}-detail`}
                                        style={{ color: c.detailColor }}>
                                        <span className={`assign-master-card-${c.recommended ? 'ivan' : c.available ? 'alexey' : 'dmitry'}-icon`}>
                                            {d.icon}
                                        </span>{' '}
                                        {d.text}
                                        {d.bold && <b style={d.boldColor ? { color: d.boldColor } : {}}>{d.bold}</b>}
                                    </div>
                                ))}

                                {c.skillTag && (
                                    <div className={`assign-master-card-${c.recommended ? 'ivan' : 'alexey'}-skills`}>
                                        <div className={`assign-master-card-${c.recommended ? 'ivan' : 'alexey'}-skill-tag`}
                                            style={{ backgroundColor: c.skillTag.bg, border: c.skillTag.border || 'none' }}>
                                            {c.skillTag.text}
                                        </div>
                                    </div>
                                )}
                            </div>

                            <div className={`assign-master-card-${c.recommended ? 'ivan' : c.available ? 'alexey' : 'dmitry'}-right`}>
                                <div className={`assign-master-card-${c.recommended ? 'ivan' : c.available ? 'alexey' : 'dmitry'}-distance`}>
                                    <div className={`assign-master-card-${c.recommended ? 'ivan' : c.available ? 'alexey' : 'dmitry'}-km`}
                                        style={{ color: c.kmColor }}>{c.km}</div>
                                    <div className={`assign-master-card-${c.recommended ? 'ivan' : c.available ? 'alexey' : 'dmitry'}-eta`}
                                        style={{ color: c.kmColor }}>{c.eta}</div>
                                </div>
                                <button className={`assign-master-card-${c.recommended ? 'ivan' : c.available ? 'alexey' : 'dmitry'}-btn`}
                                    disabled={!c.available}
                                    onClick={() => { onAssign?.(request.id, c.id); onClose() }}>
                                    {c.button.text}
                                </button>
                            </div>
                        </div>
                    ))}
                </div>

                <div className="assign-master-footer">
                    <button className="assign-master-cancel-btn" onClick={onClose}>Отмена</button>
                    <div className="assign-master-hint">Авто-подбор по алгоритму VRP</div>
                </div>
            </div>
        </div>,
        document.body
    )
}

export default EngineerReplacementModal