import { useState } from "react"
import './AuthForm.css'
import * as yup from 'yup'

const authSchema = yup.object().shape({
    login: yup
    .string()
    .required('Поля не могут быть пустыми')
    .email('Введите корректный email'),

    password: yup
    .string()
    .required('Поля не могут быть пустыми')
    .min(8, 'Не меньше 8 символов')
    .max(30, 'Не больше 30 символов')
    .matches(/^[A-Za-z0-9!@#$%^&*_+-=,.<>?]*$/, 'Пароль должен содержать только латинские буквы, цифры или символы !@#$%^&*_+-=,.<>?'),
})

const AuthForm = ({ buttonText, onSubmit }) => {
    const [login, setLogin] = useState('')
    const [password, setPassword] = useState('')
    const [validationError, setValidationError] = useState('')

    const isValid = authSchema.isValidSync({ login, password })

    const handleSubmit = async (e) => {
        e.preventDefault()

        try {
            await authSchema.validate({ login, password })
            setValidationError('')

            onSubmit({ login, password })
        } catch (error) {
            setValidationError(error.message)
        }
    }

    return (
        <form className="auth-form" onSubmit={handleSubmit} noValidate>
            <fieldset className="auth-form__fields">
                <input
                    type="email"
                    placeholder="Логин"
                    className="auth-form__input"
                    value={login}
                    onChange={(e) => setLogin(e.target.value)}
                />
                <input
                    type="password"
                    placeholder="Пароль"
                    className="auth-form__input"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                />
            </fieldset>
            {validationError && <p className="auth-form__error">{validationError}</p>}
            <button
                className={`auth-form__button ${isValid ? 'auth-form__button--active' : ''}`}
                type="submit"
            >
                {buttonText}
            </button>
        </form>
    )
}

export default AuthForm
