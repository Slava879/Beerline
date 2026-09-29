import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { setSession } from '../../api/session'
import AuthForm from '../../components/AuthForm/AuthForm'
import logoDecor from '../../assets/logo-decor.svg'
import { authRequest } from '../../api/auth'
import './AuthPage.css'

const AuthPage = () => {
    const [error, setError] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const navigate = useNavigate()

    const handleAuth = async (data) => {
    setError('')
    setIsLoading(true)
    try {
        const result = await authRequest(data)
        console.log(result)

        localStorage.setItem('access_token', result.access_token)
        localStorage.setItem('refresh_token', result.refresh_token)
        
        setSession(result.user)

        if (result.user.role === 'dispatcher') {
            navigate('/dispatcher')
        } else navigate('/auth')
        // } else if (result.user.role === 'engineer') {
        //     navigate('/engineer')
        // } else {
        //     navigate('/client')
        // }
    } catch (err) {
        setError(err.response?.data?.message || 'Что-то пошло не так')
    } finally {
        setIsLoading(false)
    }
}

    return (
        <main className="auth-page">
            <div className="auth-page__inner">
                <img src={logoDecor} alt="Билайн" className="auth-page__logo" />
                <h1 className="auth-page__title">Авторизация</h1>
                <div className="auth-card">
                    <AuthForm
                        buttonText={isLoading ? 'Загрузка...' : 'Войти'}
                        onSubmit={handleAuth}
                    />
                </div>
                {error && <p className="auth-page__error">{error}</p>}
            </div>
        </main>
    )
}

export default AuthPage
