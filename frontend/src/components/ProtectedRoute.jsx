import { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import clienteAxios from "./auth/axiosConfig";

// `esqueleto`: lo que se ve mientras se verifica la sesión (el panel entero, en la ruta del admin)
export default function ProtectedRoute({ allowedRoles, esqueleto }) {
    // Sin token no hay nada que verificar: se redirige al login de inmediato
    const [cargando, setCargando] = useState(() => Boolean(localStorage.getItem('access_token')));
    const [autenticado, setAutenticado] = useState(false);
    const [rol, setRol] = useState(null);

    useEffect(() => {
        if (!localStorage.getItem('access_token')) return;

        // Usamos la ruta relativa, clienteAxios pone el baseURL y el Header
        clienteAxios.get('usuarios/me/')
        .then((respuesta) => {
            setAutenticado(true);
            setRol(respuesta.data.rol);
            localStorage.setItem('rol', respuesta.data.rol);
        })
        .catch(() => {
            // Limpiamos todo el rastro si el token expiró o es inválido
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('rol');
            setAutenticado(false);
        })
        .finally(() => {
            setCargando(false);
        });
    }, []);

    if (cargando) {
        if (esqueleto) return esqueleto;
        return <main id="contenido" tabIndex={-1}><p role="status">Verificando sesión...</p></main>;
    }

    if (!autenticado) {
        return <Navigate to="/login" replace />;
    }

    if (allowedRoles && !allowedRoles.includes(rol)) {
        return <Navigate to="/login" replace />; // O a una página de "No Autorizado"
    }

    return <Outlet />;
}
