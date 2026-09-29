import logoDecor from '../../assets/logo-decor.svg'
import './AuthHeader.css'

const AuthHeader = () => {
    return (
        <header className='header'>
            <div className="container auth-header__container">
                <svg width="73" height="73">
                    <use href={logoDecor}></use>
                </svg>
            </div>
        </header>
    )
}

export default AuthHeader