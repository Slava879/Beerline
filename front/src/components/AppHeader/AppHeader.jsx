import { Link } from 'react-router-dom'
import { useState } from 'react'
import logo from '../../assets/beeline-seeklogo.svg'
import profileIcon from '../../assets/icon-profile.svg'
import './AppHeader.css'
import ProfileModal from '../ProfileModal/ProfileModal'

// Шапка с логотипом и кнопкой профиля. По факту дублирует PageHeader.jsx (тот же
// логотип + кнопка профиля, но без обёртки в фрагмент и с другой версткой отступов) —
// сейчас используется не везде, вместо него на страницах диспетчера/инженера стоит
// PageHeader. Стоит решить с командой, нужны ли оба компонента, или это два черновика
// одного и того же от разных этапов вёрстки.
const AppHeader = () => {
    const [isProfileOpen, setIsProfileOpen] = useState(false)

    return (
        <header className="menu__header">
            <div className="header__container">
                <Link to="/" className="header__link-logo">
                    <img src={logo} width={44} height={44} alt="Билайн" />
                </Link>
                <div className="header__mini-container">
                    <button
                        type="button"
                        className="header__link-profile"
                        onClick={() => setIsProfileOpen(true)}
                        aria-label="Открыть профиль"
                    >
                        <img src={profileIcon} width={36} height={40} alt="" />
                    </button>
                </div>
            </div>
            <ProfileModal
                isOpen={isProfileOpen}
                onClose={() => setIsProfileOpen(false)}
            />
        </header>
    )
}

export default AppHeader