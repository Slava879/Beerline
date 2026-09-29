import { BrowserRouter, Route, Routes } from "react-router-dom"
import AuthPage from "./pages/AuthPage/AuthPage"
import DispatcherPage from "./pages/DispatcherPage/DispatcherPage"
import EngineerPage from "./pages/EngineerPage/EngineerPage"
import ProtectedRoute from "./components/ProtectedRoute/ProtectedRoute"

const App = () => {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<AuthPage />} />

                <Route
                        path="/dispatcher"
                        element={
                            <ProtectedRoute allowedRoles={['dispatcher']}>
                                <DispatcherPage />
                            </ProtectedRoute>
                        }
                    />
                <Route
                    path="/engineer"
                    element={
                        <ProtectedRoute allowedRoles={['engineer']}>
                            <EngineerPage />
                        </ProtectedRoute>
                    }
                />
            </Routes>
        </BrowserRouter>
    )
}

export default App