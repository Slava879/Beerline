import { createPortal } from 'react-dom'
import profileIcon from '../../assets/icon-profile.svg'
import onlineIcon from '../../assets/online-icon.svg'
import { profileData } from './mockData'
import { getSession } from '../../api/session'
// 🔌 БЭКЕНД: profileData (план/маршрут/багажник) сейчас мок, а user (имя/роль) —
// из localStorage (кладётся при логине). Когда появится GET /profile, можно
// заменить оба источника на один вызов getProfile() из '../../api/profile'.

const ProfileModal = ({ isOpen, onClose }) => {
    if (!isOpen) return null

    const user = getSession() || { name: 'Иван Петров', role: 'engineer' }
    const roleText = user.role === 'dispatcher' ? 'Диспетчер WFM' : 'Инженер WFM'

    return createPortal(
        <div
            style={{
                position: 'fixed', inset: 0, zIndex: 1000,
                background: 'rgba(15,23,42,0.55)',
                display: 'flex', justifyContent: 'flex-start', alignItems: 'flex-start',
                padding: 20, overflowY: 'auto',
            }}
            onClick={onClose}
        >
            <div
                className="profile__section"
                style={{
                    height: 'auto', minHeight: 'unset', width: '100%', maxWidth: 736,
                    borderTop: 'none', borderRadius: 12, overflow: 'hidden',
                    backgroundColor: '#fff',
                    boxShadow: '0 20px 40px rgba(0,0,0,0.15)',
                }}
                onClick={(e) => e.stopPropagation()}
            >
                <div className="profile__container" style={{ maxWidth: '100%' }}>
                    <header className="profile__header" style={{ position: 'relative' }}>
                        <button
                            type="button"
                            onClick={onClose}
                            aria-label="Закрыть"
                            style={{
                                position: 'absolute', top: 12, right: 14, zIndex: 2,
                                background: 'none', border: 'none', fontSize: 25,
                                lineHeight: 1, color: '#94A3B8', cursor: 'pointer', padding: '0 5px',
                            }}
                        >
                            ×
                        </button>
                        <div className="profile__header-container" style={{ gap: 20, paddingRight: 52 }}>
                            <div className="profile__header-info">
                                <div className="profile__header-link">
                                    <img src={profileIcon} width={36} height={40} alt="Профиль" />
                                </div>
                                <div className="profile__header-info-description">
                                    <p className="profile__name">{user.name}</p>
                                    <p className="profile__post">{roleText} • ID: #ENG-104</p>
                                </div>
                            </div>
                            <div className="profile__status" style={{ padding: '11px 24px 11px 16px', whiteSpace: 'nowrap' }}>
                                <img src={onlineIcon} width={13} height={13} alt="" />
                                <p className="profile__status-text">{profileData.status}</p>
                            </div>
                        </div>
                    </header>

                    <div className="profile__main">
                        <div className="profile__container">
                            <div className="profile__info">
                                <p className="profile__plan">
                                    План на день:{' '}
                                    <span className="profile__plan--accent">{profileData.plan}</span>
                                </p>
                                <p className="profile__route">
                                    Маршрут:{' '}
                                    <span className="profile__route--accent">{profileData.route}</span>
                                </p>
                                <p className="profile__trunk">{profileData.trunk}</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>,
        document.body
    )
}

export default ProfileModal
