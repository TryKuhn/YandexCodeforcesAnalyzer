import {BrowserRouter, Routes, Route, Navigate} from 'react-router-dom';
import {Landing} from './pages/Landing';
import {LoginPage} from './pages/LoginPage';
import {RegisterPage} from './pages/RegisterPage';
import {useAuthStore} from './store/useAuthStore';
import {ThemeInitializer} from "./components/ThemeInitializer.tsx";
import {MainLayout} from "./components/layout/MainLayout.tsx";
import {AuthInitializer} from "./components/AuthInitializer.tsx";
import {NotFound} from "./pages/NotFound.tsx";
import {Docs} from "./pages/Docs.tsx";
import {JuryGuard} from "./components/JuryGuard.tsx";
import {portalRoutes} from "@portal-routes";

function App() {
    const {isAuthenticated} = useAuthStore();

    return (
        <BrowserRouter>
            <AuthInitializer/>
            <ThemeInitializer/>
            <Routes>
                <Route path="/login" element={isAuthenticated ? <Navigate to="/" replace/> : <LoginPage/>}/>
                <Route path="/register" element={isAuthenticated ? <Navigate to="/" replace/> : <RegisterPage/>}/>

                <Route
                    path="/"
                    element={
                        isAuthenticated ? (
                            <JuryGuard><MainLayout/></JuryGuard>
                        ) : (
                            <Landing/>
                        )
                    }
                >
                    {/* vite swaps this import per portal, so only one route set ships */}
                    {portalRoutes}
                </Route>

                <Route path="/docs" element={<Docs/>}/>

                <Route path="*" element={<NotFound/>}/>
            </Routes>
        </BrowserRouter>
    );
}

export default App;
