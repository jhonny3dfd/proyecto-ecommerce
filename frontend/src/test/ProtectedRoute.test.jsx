import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import ProtectedRoute from '../components/ProtectedRoute';
import clienteAxios from '../components/auth/axiosConfig';

vi.mock('../components/auth/axiosConfig', () => ({
    default: {
        get: vi.fn(),
    },
}));

function UbicacionActual() {
    const location = useLocation();
    return <p>Ruta actual: {location.pathname}</p>;
}

function PaginaProtegida() {
    return <h1>Contenido protegido</h1>;
}

function PaginaLogin() {
    return <h1>Página de inicio de sesión</h1>;
}

function renderizarRuta(allowedRoles) {
    return render(
        <MemoryRouter initialEntries={['/privado']}>
            <Routes>
                <Route path="/login" element={<PaginaLogin />} />
                <Route
                    path="/privado"
                    element={<ProtectedRoute allowedRoles={allowedRoles} />}
                >
                    <Route index element={<PaginaProtegida />} />
                </Route>
                <Route
                    path="*"
                    element={<UbicacionActual />}
                />
            </Routes>
        </MemoryRouter>
    );
}

describe('ProtectedRoute', () => {
    beforeEach(() => {
        localStorage.clear();
        vi.clearAllMocks();
    });

    afterEach(() => {
        cleanup();
    });

    it('redirige al login cuando no existe token', () => {
        renderizarRuta();

        expect(screen.getByRole('heading', {
            name: 'Página de inicio de sesión',
        })).toBeInTheDocument();

        expect(clienteAxios.get).not.toHaveBeenCalled();
    });

    it('muestra el mensaje de verificación cuando hay token', () => {
        localStorage.setItem('access_token', 'token-valido');
        clienteAxios.get.mockReturnValue(new Promise(() => {}));

        renderizarRuta();

        expect(screen.getByRole('status')).toHaveTextContent('Verificando sesión...');
        expect(clienteAxios.get).toHaveBeenCalledWith('usuarios/me/');
    });

    it('permite el acceso cuando el usuario está autenticado', async () => {
        localStorage.setItem('access_token', 'token-valido');
        clienteAxios.get.mockResolvedValue({
            data: { rol: 'CLIENTE' },
        });

        renderizarRuta();

        expect(await screen.findByRole('heading', {
            name: 'Contenido protegido',
        })).toBeInTheDocument();

        expect(localStorage.getItem('rol')).toBe('CLIENTE');
    });

    it('permite el acceso si no se especifican roles permitidos', async () => {
        localStorage.setItem('access_token', 'token-valido');
        clienteAxios.get.mockResolvedValue({
            data: { rol: 'CLIENTE' },
        });

        renderizarRuta(undefined);

        expect(await screen.findByRole('heading', {
            name: 'Contenido protegido',
        })).toBeInTheDocument();
    });

    it('redirige al login si el rol no está permitido', async () => {
        localStorage.setItem('access_token', 'token-valido');
        clienteAxios.get.mockResolvedValue({
            data: { rol: 'CLIENTE' },
        });

        renderizarRuta(['ADMIN']);

        expect(await screen.findByRole('heading', {
            name: 'Página de inicio de sesión',
        })).toBeInTheDocument();
    });

    it('limpia los tokens y el rol si falla la verificación', async () => {
        localStorage.setItem('access_token', 'token-expirado');
        localStorage.setItem('refresh_token', 'refresh-expirado');
        localStorage.setItem('rol', 'ADMIN');

        clienteAxios.get.mockRejectedValue(new Error('Token inválido'));

        renderizarRuta();

        expect(await screen.findByRole('heading', {
            name: 'Página de inicio de sesión',
        })).toBeInTheDocument();

        await waitFor(() => {
            expect(localStorage.getItem('access_token')).toBeNull();
            expect(localStorage.getItem('refresh_token')).toBeNull();
            expect(localStorage.getItem('rol')).toBeNull();
        });
    });
});
