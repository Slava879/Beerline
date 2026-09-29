import { useState } from 'react'
import { Link } from 'react-router-dom'
import beelineLogo from '../../assets/beeline-seeklogo.svg'
import profileIcon from '../../assets/icon-profile.svg'
import ProfileModal from '../ProfileModal/ProfileModal'

// Шапка страницы (лого + кнопка открытия профиля). Используется на DispatcherPage
// и EngineerPage. См. также AppHeader.jsx — очень похожий компонент, оставлен
// на данный момент как есть, чтобы не трогать вёрстку без согласования с дизайнером.
const PageHeader = () => {
    const [isProfileOpen, setIsProfileOpen] = useState(false)

    return (
        <>
            <header className="menu__header">
                <div className="header__container">
                    <Link to="/" className="header__link-logo">
                        <img src={beelineLogo} alt="Билайн" width="44" height="44" />
                    </Link>
                    <div className="header__mini-container">
                        <button
                            type="button"
                            className="header__link-profile"
                            style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
                        >
                            <img src={profileIcon} alt="Профиль" width="36" height="40" />
                        </button>
                    </div>
                </div>
            </header>
            <ProfileModal isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
        </>
    )
}

export default PageHeader
