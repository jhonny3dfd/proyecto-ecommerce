import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import {cleanup,render,screen,fireEvent,waitFor,} from '@testing-library/react';
import Register from '../components/auth/Register';
import clienteAxios from '../components/auth/axiosConfig';

vi.mock('../components/auth/axiosConfig', () => ({
    default: {
        post: vi.fn(),
    },
}));

describe('Register', () => {
    const onSwitchToLogin = vi.fn();

    beforeEach(() => {
        vi.clearAllMocks();
        clienteAxios.post.mockReset();
        clienteAxios.post.mockResolvedValue({ data: {} });
    });

    afterEach(() => {
        cleanup();
        vi.restoreAllMocks();
    });

    const completarFormulario = () => {
        fireEvent.change(screen.getByLabelText('Nombre'), {
            target: { value: 'Juan' },
        });
        fireEvent.change(screen.getByLabelText('Apellido paterno'), {
            target: { value: 'Pérez' },
        });
        fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
            target: { value: 'juan@ejemplo.com' },
        });
        fireEvent.change(screen.getByLabelText('Contraseña'), {
            target: { value: 'ClaveSegura123' },
        });
        fireEvent.change(screen.getByLabelText('Confirmar contraseña'), {
            target: { value: 'ClaveSegura123' },
        });
    };

    const enviarFormulario = () => {
        completarFormulario();
        fireEvent.click(screen.getByRole('button', { name: 'Registrarse' }));
    };

    it('muestra el formulario de registro', () => {
        render(<Register onSwitchToLogin={onSwitchToLogin} />);

        expect(
            screen.getByRole('heading', { name: 'Crear cuenta' })
        ).toBeTruthy();

        expect(screen.getByLabelText('Nombre')).toBeTruthy();
        expect(screen.getByLabelText('Apellido paterno')).toBeTruthy();
        expect(screen.getByLabelText(/correo electrónico/i)).toBeTruthy();
        expect(screen.getByLabelText('Contraseña')).toBeTruthy();
        expect(screen.getByLabelText('Confirmar contraseña')).toBeTruthy();
        expect(
            screen.getByRole('button', { name: 'Registrarse' })
        ).toBeTruthy();
    });

    it('muestra los campos obligatorios y sus tipos de entrada', () => {
        render(<Register onSwitchToLogin={onSwitchToLogin} />);

        expect(screen.getByLabelText('Nombre').required).toBe(true);
        expect(screen.getByLabelText('Apellido paterno').required).toBe(true);
        expect(screen.getByLabelText(/correo electrónico/i).type).toBe('email');
        expect(screen.getByLabelText('Contraseña').type).toBe('password');
        expect(
            screen.getByLabelText('Confirmar contraseña').type
        ).toBe('password');
    });

    it('avisa cuando las contraseñas no coinciden y no llama al backend', async () => {
        render(<Register onSwitchToLogin={onSwitchToLogin} />);

        completarFormulario();

        fireEvent.change(screen.getByLabelText('Confirmar contraseña'), {
            target: { value: 'OtraClave123' },
        });

        fireEvent.click(screen.getByRole('button', { name: 'Registrarse' }));

        expect((await screen.findByRole('alert')).textContent).toBe(
            'Revisa los datos marcados.'
        );
        expect(screen.getByText('Las contraseñas no coinciden.')).toBeTruthy();
        expect(
            screen.getByLabelText('Confirmar contraseña').getAttribute('aria-invalid')
        ).toBe('true');
        expect(clienteAxios.post).not.toHaveBeenCalled();
    });

    it('crea la cuenta y vuelve al login con el correo y el aviso', async () => {
        render(<Register onSwitchToLogin={onSwitchToLogin} />);

        enviarFormulario();

        await waitFor(() => {
            expect(onSwitchToLogin).toHaveBeenCalledWith({
                texto: 'Tu cuenta quedó creada. Ya puedes iniciar sesión.',
                email: 'juan@ejemplo.com',
            });
        });

        expect(clienteAxios.post).toHaveBeenCalledWith('/usuarios/registro/', {
            nombre: 'Juan',
            apellido_paterno: 'Pérez',
            email: 'juan@ejemplo.com',
            password: 'ClaveSegura123',
            password2: 'ClaveSegura123',
        });
    });

    it('permite volver al login sin enviar el formulario', () => {
        render(<Register onSwitchToLogin={onSwitchToLogin} />);

        fireEvent.click(
            screen.getByRole('button', { name: /inicia sesión aquí/i })
        );

        expect(onSwitchToLogin).toHaveBeenCalledTimes(1);
        expect(onSwitchToLogin).toHaveBeenCalledWith();
        expect(clienteAxios.post).not.toHaveBeenCalled();
    });

    it('muestra los errores de validación que devuelve el backend', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});

        clienteAxios.post.mockRejectedValue({
            response: {
                status: 400,
                data: {
                    email: ['Este correo ya está registrado.'],
                    password: ['La contraseña es demasiado corta.'],
                },
            },
        });

        render(<Register onSwitchToLogin={onSwitchToLogin} />);

        enviarFormulario();

        expect(
            await screen.findByText('Este correo ya está registrado.')
        ).toBeTruthy();
        expect(
            screen.getByText('La contraseña es demasiado corta.')
        ).toBeTruthy();

        expect(
            screen.getByLabelText(/correo electrónico/i).getAttribute('aria-invalid')
        ).toBe('true');
        expect(
            screen.getByLabelText('Contraseña').getAttribute('aria-invalid')
        ).toBe('true');

        expect(
            screen.getByRole('alert').textContent
        ).toBe('Revisa los datos marcados.');
    });

    it('muestra errores generales del backend que no pertenecen a un campo', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});

        clienteAxios.post.mockRejectedValue({
            response: {
                status: 400,
                data: {
                    detail: ['No se pudo crear el usuario.'],
                    email: ['Correo inválido.'],
                },
            },
        });

        render(<Register onSwitchToLogin={onSwitchToLogin} />);

        enviarFormulario();

        expect(
            await screen.findByRole('alert')
        ).toHaveProperty('textContent', 'No se pudo crear el usuario.');

        expect(await screen.findByText('Correo inválido.')).toBeTruthy();
    });

    it('combina varios mensajes de validación en un mismo campo', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});

        clienteAxios.post.mockRejectedValue({
            response: {
                status: 400,
                data: {
                    email: [
                        'El correo no es válido.',
                        'El correo ya existe.',
                    ],
                },
            },
        });

        render(<Register onSwitchToLogin={onSwitchToLogin} />);

        enviarFormulario();

        expect(
            await screen.findByText(
                'El correo no es válido. El correo ya existe.'
            )
        ).toBeTruthy();
    });

    it('muestra un mensaje si no hay conexión con la tienda', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});

        clienteAxios.post.mockRejectedValue(new Error('Sin conexión'));

        render(<Register onSwitchToLogin={onSwitchToLogin} />);

        enviarFormulario();

        expect(
            (await screen.findByRole('alert')).textContent
        ).toBe(
            'No pudimos conectar con la tienda. Revisa tu conexión e inténtalo de nuevo.'
        );

        expect(
            screen.getByRole('button', { name: 'Registrarse' }).disabled
        ).toBe(false);
    });

    it('muestra un mensaje genérico ante errores distintos de validación', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});

        clienteAxios.post.mockRejectedValue({
            response: {
                status: 500,
                data: { detail: 'Error interno' },
            },
        });

        render(<Register onSwitchToLogin={onSwitchToLogin} />);

        enviarFormulario();

        expect(
            (await screen.findByRole('alert')).textContent
        ).toBe('No pudimos crear tu cuenta. Inténtalo de nuevo.');
    });

    it('muestra un mensaje genérico si el backend devuelve datos inválidos', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});

        clienteAxios.post.mockRejectedValue({
            response: {
                status: 400,
                data: null,
            },
        });

        render(<Register onSwitchToLogin={onSwitchToLogin} />);

        enviarFormulario();

        expect(
            (await screen.findByRole('alert')).textContent
        ).toBe('No pudimos crear tu cuenta. Inténtalo de nuevo.');
    });

    it('deshabilita el botón mientras se procesa el registro', async () => {
        let resolver;

        clienteAxios.post.mockReturnValue(
            new Promise((resolve) => {
                resolver = resolve;
            })
        );

        render(<Register onSwitchToLogin={onSwitchToLogin} />);

        enviarFormulario();

        expect(
            screen.getByRole('button', { name: 'Creando cuenta...' }).disabled
        ).toBe(true);

        resolver({ data: {} });

        await waitFor(() => {
            expect(onSwitchToLogin).toHaveBeenCalledTimes(1);
        });
    });
});
