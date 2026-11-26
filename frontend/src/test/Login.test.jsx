import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import {cleanup,render,screen,fireEvent,waitFor,} from '@testing-library/react';
import Login from '../components/auth/Login';
import clienteAxios from '../components/auth/axiosConfig';

const mocks = vi.hoisted(() => ({
    navigate: vi.fn(),
    guardarCarrito: vi.fn(),
}));

vi.mock('../components/auth/axiosConfig', () => ({
    default: {
        post: vi.fn(),
        get: vi.fn(),
    },
}));

vi.mock('react-router-dom', () => ({
    useNavigate: () => mocks.navigate,
    Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
}));

vi.mock('../components/carrito', () => ({
    guardarCarrito: mocks.guardarCarrito,
}));

vi.mock('@react-oauth/google', () => ({
    GoogleLogin: ({ onSuccess, onError }) => (
        <div>
            <button
                type="button"
                onClick={() => onSuccess({ credential: 'google-token-prueba' })}
            >
                Simular Google exitoso
            </button>
            <button type="button" onClick={onError}>
                Simular error de Google
            </button>
        </div>
    ),
}));

describe('Login', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        localStorage.clear();

        clienteAxios.post.mockReset();
        clienteAxios.get.mockReset();

        clienteAxios.post.mockResolvedValue({ data: {} });
        clienteAxios.get.mockImplementation(async (url) => {
            if (url === 'usuarios/me/') {
                return { data: { rol: 'CLIENTE' } };
            }

            if (url === 'ventas/carrito/') {
                return { data: [] };
            }

            throw new Error(`URL inesperada: ${url}`);
        });

        mocks.guardarCarrito.mockResolvedValue(undefined);
    });

    afterEach(() => {
        cleanup();
        vi.restoreAllMocks();
    });

    const completarFormulario = () => {
        fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
            target: { value: 'cliente@ejemplo.com' },
        });

        fireEvent.change(screen.getByLabelText(/contraseña/i), {
            target: { value: 'ClaveSegura123' },
        });
    };

    const enviarFormulario = () => {
        completarFormulario();
        fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    };

    it('muestra el formulario de inicio de sesión', () => {
        render(<Login />);

        expect(
            screen.getByRole('heading', { name: /iniciar sesión/i })
        ).toBeTruthy();
        expect(screen.getByLabelText(/correo electrónico/i)).toBeTruthy();
        expect(screen.getByLabelText(/contraseña/i)).toBeTruthy();
        expect(screen.getByRole('button', { name: 'Entrar' })).toBeTruthy();
    });

    it('ofrece recuperar la contraseña olvidada', () => {
        render(<Login />);

        expect(screen.getByRole('link', { name: '¿Olvidaste tu contraseña?' }).getAttribute('href'))
            .toBe('/recuperar-contrasena');
    });

    it('precarga el correo y muestra el aviso de registro cuando se reciben', () => {
        render(
            <Login
                aviso={{
                    email: 'nuevo@ejemplo.com',
                    texto: 'Tu cuenta fue creada correctamente.',
                }}
            />
        );

        expect(screen.getByLabelText(/correo electrónico/i).value).toBe(
            'nuevo@ejemplo.com'
        );
        expect(
            screen.getByRole('status').textContent
        ).toContain('Tu cuenta fue creada correctamente.');
    });

    it('llama a onSwitchToRegister al pulsar el botón de registro', () => {
        const onSwitchToRegister = vi.fn();

        render(<Login onSwitchToRegister={onSwitchToRegister} />);

        fireEvent.click(
            screen.getByRole('button', { name: /regístrate aquí/i })
        );

        expect(onSwitchToRegister).toHaveBeenCalledTimes(1);
    });

    it('inicia sesión como cliente y navega al catálogo', async () => {
        render(<Login />);

        enviarFormulario();

        await waitFor(() => {
            expect(mocks.navigate).toHaveBeenCalledWith('/catalogo');
        });

        expect(clienteAxios.post).toHaveBeenCalledWith('usuarios/token/', {
            email: 'cliente@ejemplo.com',
            password: 'ClaveSegura123',
        });
        expect(clienteAxios.get).toHaveBeenCalledWith('usuarios/me/');
        expect(clienteAxios.get).toHaveBeenCalledWith('ventas/carrito/');
        expect(mocks.guardarCarrito).toHaveBeenCalledWith([]);
    });

    it('navega al panel de administración si el rol es ADMIN', async () => {
        clienteAxios.get.mockImplementation(async (url) => {
            if (url === 'usuarios/me/') {
                return { data: { rol: 'ADMIN' } };
            }

            return { data: [] };
        });

        render(<Login />);

        enviarFormulario();

        await waitFor(() => {
            expect(mocks.navigate).toHaveBeenCalledWith('/admin');
        });
    });

    it('vuelve a la URL anterior si existe', async () => {
        localStorage.setItem(
            'url_anterior_login',
            '/checkout'
        );

        render(<Login />);

        enviarFormulario();

        await waitFor(() => {
            expect(mocks.navigate).toHaveBeenCalledWith('/checkout');
        });

        expect(localStorage.getItem('url_anterior_login')).toBeNull();
    });

    it('muestra un mensaje si las credenciales son incorrectas', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});

        clienteAxios.post.mockRejectedValue({
            response: { status: 401 },
        });

        render(<Login />);

        enviarFormulario();

        expect(
            (await screen.findByRole('alert')).textContent
        ).toBe('Correo o contraseña incorrectos.');

        expect(mocks.navigate).not.toHaveBeenCalled();
        expect(screen.getByRole('button', { name: 'Entrar' }).disabled).toBe(
            false
        );
    });

    it('muestra un mensaje si no hay conexión con la tienda', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});

        clienteAxios.post.mockRejectedValue(new Error('Sin conexión'));

        render(<Login />);

        enviarFormulario();

        expect(
            (await screen.findByRole('alert')).textContent
        ).toContain('No pudimos conectar con la tienda.');
    });

    it('muestra un mensaje genérico ante otros errores del servidor', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});

        clienteAxios.post.mockRejectedValue({
            response: { status: 500 },
        });

        render(<Login />);

        enviarFormulario();

        expect(
            (await screen.findByRole('alert')).textContent
        ).toBe('No pudimos iniciar sesión. Inténtalo de nuevo.');
    });

    it('no muestra la opción de Google cuando está deshabilitada', () => {
        render(<Login />);

        expect(
            screen.queryByRole('button', { name: /simular google/i })
        ).toBeNull();
    });

    it('inicia sesión con Google y guarda los tokens', async () => {
        clienteAxios.post.mockImplementation(async (url) => {
            if (url === 'usuarios/google/') {
                return {
                    data: {
                        tokens: {
                            access: 'google-access',
                            refresh: 'google-refresh',
                        },
                    },
                };
            }

            return { data: {} };
        });

        render(<Login googleHabilitado />);

        fireEvent.click(
            screen.getByRole('button', { name: /simular google exitoso/i })
        );

        await waitFor(() => {
            expect(mocks.navigate).toHaveBeenCalledWith('/catalogo');
        });

        expect(clienteAxios.post).toHaveBeenCalledWith('usuarios/google/', {
            id_token: 'google-token-prueba',
        });
        expect(localStorage.getItem('access_token')).toBe('google-access');
        expect(localStorage.getItem('refresh_token')).toBe('google-refresh');
    });

    it('muestra un mensaje cuando Google informa un error', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});

        render(<Login googleHabilitado />);

        fireEvent.click(
            screen.getByRole('button', { name: /simular error de google/i })
        );

        expect(
            (await screen.findByRole('alert')).textContent
        ).toBe('No se pudo completar el acceso con Google.');
    });

    it('no bloquea el inicio de sesión si falla la sincronización del carrito', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});

        mocks.guardarCarrito.mockRejectedValue(
            new Error('No se pudo guardar el carrito')
        );

        render(<Login />);

        enviarFormulario();

        await waitFor(() => {
            expect(mocks.navigate).toHaveBeenCalledWith('/catalogo');
        });
    });

    it('combina el carrito de invitado con el de la cuenta', async () => {
        localStorage.setItem(
            'carrito_local',
            JSON.stringify([
                {
                    id: 'producto-1',
                    sku: 'SKU-1',
                    nombre: 'Producto local',
                    precio: 1000,
                    cantidad: 2,
                },
                {
                    id: 'producto-2',
                    sku: 'SKU-2',
                    nombre: 'Producto nuevo',
                    precio: 2000,
                    cantidad: 1,
                },
            ])
        );

        clienteAxios.get.mockImplementation(async (url) => {
            if (url === 'usuarios/me/') {
                return { data: { rol: 'CLIENTE' } };
            }

            if (url === 'ventas/carrito/') {
                return {
                    data: [
                        {
                            producto_mongo_id: 'producto-1',
                            variante_sku: 'SKU-1',
                            nombre: 'Producto cuenta',
                            precio: '1000',
                            cantidad: 3,
                        },
                    ],
                };
            }

            throw new Error(`URL inesperada: ${url}`);
        });

        render(<Login />);

        enviarFormulario();

        await waitFor(() => {
            expect(mocks.guardarCarrito).toHaveBeenCalledTimes(1);
        });

        const carritoGuardado = mocks.guardarCarrito.mock.calls[0][0];

        expect(carritoGuardado).toHaveLength(2);
        expect(
            carritoGuardado.find((item) => item.sku === 'SKU-1').cantidad
        ).toBe(5);
        expect(
            carritoGuardado.find((item) => item.sku === 'SKU-2').cantidad
        ).toBe(1);
    });
});
