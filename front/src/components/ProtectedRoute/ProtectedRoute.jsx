import { Navigate, useLocation } from 'react-router-dom'
import { getSession } from '../../api/session'

const ProtectedRoute = ({ allowedRoles, children }) => {
    const location = useLocation()
    const session = getSession()

    if (!session?.user) {
        return <Navigate to="/auth" state={{ from: location }} replace />
    }

    if (allowedRoles && !allowedRoles.includes(session.user.role)) {
        const home =
            session.user.role === 'dispatcher' ? '/dispatcher'
            : session.user.role === 'engineer' ? '/engineer'
            : '/client'
        return <Navigate to={home} replace />
    }

    return children
}

export default ProtectedRoute