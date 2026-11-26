import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
    client: vi.fn(),
    create: vi.fn(),
    post: vi.fn(),
    requestUse: vi.fn(),
    responseUse: vi.fn(),
}));

vi.mock('axios', () => ({
    default: {
        create: mocks.create,
        post: mocks.post,
    },
}));

describe('axiosConfig', () => {
    let clienteAxios;
    let interceptorPeticion;
    let interceptorRespuesta;
    let interceptorError;

    beforeEach(async () => {
        vi.resetModules();
        localStorage.clear();
        vi.clearAllMocks();

        mocks.client.mockReset();
        mocks.client.mockResolvedValue({ data: { ok: true } });
        mocks.post.mockReset();
        mocks.requestUse.mockReset();
        mocks.responseUse.mockReset();

        mocks.create.mockImplementation(() => {
            mocks.client.interceptors = {
                request: { use: mocks.requestUse },
                response: { use: mocks.responseUse },
            };

            return mocks.client;
        });

        ({ default: clienteAxios } = await import(
            '../components/auth/axiosConfig'
        ));

        interceptorPeticion = mocks.requestUse.mock.calls[0][0];

        const [respuesta, error] = mocks.responseUse.mock.calls[0];
        interceptorRespuesta = respuesta;
        interceptorError = error;
    });

    it('crea Axios con la URL base y el tipo de contenido esperados', () => {
        expect(mocks.create).toHaveBeenCalledWith({
            baseURL: 'http://localhost:8000/api/',
            headers: {
                'Content-Type': 'application/json',
            },
        });
        expect(clienteAxios).toBe(mocks.client);
    });

    it('agrega el token de acceso a la petición cuando existe', () => {
        localStorage.setItem('access_token', 'token-prueba');

        const config = { headers: {} };
        const resultado = interceptorPeticion(config);

        expect(resultado.headers.Authorization).toBe(
            'Bearer token-prueba'
        );
    });

    it('no agrega autorización si no existe un token', () => {
        const config = { headers: {} };

        const resultado = interceptorPeticion(config);

        expect(resultado.headers.Authorization).toBeUndefined();
    });

    it('guarda los JWT recibidos en una respuesta exitosa', () => {
        const respuesta = {
            data: {
                access: 'access-nuevo',
                refresh: 'refresh-nuevo',
            },
        };

        const resultado = interceptorRespuesta(respuesta);

        expect(localStorage.getItem('access_token')).toBe('access-nuevo');
        expect(localStorage.getItem('refresh_token')).toBe('refresh-nuevo');
        expect(resultado).toBe(respuesta);
    });

    it('devuelve la respuesta si no contiene un token', () => {
        const respuesta = { data: { mensaje: 'Correcto' } };

        expect(interceptorRespuesta(respuesta)).toBe(respuesta);
        expect(localStorage.getItem('access_token')).toBeNull();
    });

    it('renueva el token y reintenta una petición que recibe 401', async () => {
        localStorage.setItem('access_token', 'access-vencido');
        localStorage.setItem('refresh_token', 'refresh-valido');

        const original = {
            headers: {
                Authorization: 'Bearer access-vencido',
            },
        };
        const error = {
            config: original,
            response: { status: 401 },
        };

        mocks.post.mockResolvedValue({
            data: { access: 'access-renovado' },
        });

        const respuestaEsperada = { data: { ok: true } };
        mocks.client.mockResolvedValue(respuestaEsperada);

        const resultado = await interceptorError(error);

        expect(mocks.post).toHaveBeenCalledWith(
            'http://localhost:8000/api/usuarios/token/refresh/',
            { refresh: 'refresh-valido' }
        );
        expect(original._reintentado).toBe(true);
        expect(original.headers.Authorization).toBe(
            'Bearer access-renovado'
        );
        expect(localStorage.getItem('access_token')).toBe(
            'access-renovado'
        );
        expect(mocks.client).toHaveBeenCalledWith(original);
        expect(resultado).toBe(respuestaEsperada);
    });

    it('limpia la sesión si falla la renovación del token', async () => {
        localStorage.setItem('access_token', 'access-vencido');
        localStorage.setItem('refresh_token', 'refresh-invalido');
        localStorage.setItem('rol', 'ADMIN');

        const original = {
            headers: {
                Authorization: 'Bearer access-vencido',
            },
        };
        const error = {
            config: original,
            response: { status: 401 },
        };

        mocks.post.mockRejectedValue(new Error('Refresh inválido'));

        await interceptorError(error);

        expect(localStorage.getItem('access_token')).toBeNull();
        expect(localStorage.getItem('refresh_token')).toBeNull();
        expect(localStorage.getItem('rol')).toBeNull();
        expect(original.headers.Authorization).toBeUndefined();
        expect(mocks.client).toHaveBeenCalledWith(original);
    });

    it('no intenta renovar si la petición no llevaba token', async () => {
        const error = {
            config: { headers: {} },
            response: { status: 401 },
        };

        await expect(interceptorError(error)).rejects.toBe(error);

        expect(mocks.post).not.toHaveBeenCalled();
        expect(mocks.client).not.toHaveBeenCalled();
    });

    it('no reintenta una petición que ya fue reintentada', async () => {
        localStorage.setItem('refresh_token', 'refresh-valido');

        const error = {
            config: {
                headers: { Authorization: 'Bearer access-vencido' },
                _reintentado: true,
            },
            response: { status: 401 },
        };

        await expect(interceptorError(error)).rejects.toBe(error);

        expect(mocks.post).not.toHaveBeenCalled();
        expect(mocks.client).not.toHaveBeenCalled();
    });

    it('no renueva el token para errores que no son 401', async () => {
        const error = {
            config: {
                headers: { Authorization: 'Bearer token' },
            },
            response: { status: 500 },
        };

        await expect(interceptorError(error)).rejects.toBe(error);

        expect(mocks.post).not.toHaveBeenCalled();
    });

    it('limpia la sesión cuando no existe refresh_token', async () => {
        localStorage.setItem('access_token', 'access-vencido');
        localStorage.setItem('rol', 'CLIENTE');

        const original = {
            headers: {
                Authorization: 'Bearer access-vencido',
            },
        };
        const error = {
            config: original,
            response: { status: 401 },
        };

        await interceptorError(error);

        expect(mocks.post).not.toHaveBeenCalled();
        expect(localStorage.getItem('access_token')).toBeNull();
        expect(localStorage.getItem('rol')).toBeNull();
        expect(original.headers.Authorization).toBeUndefined();
        expect(mocks.client).toHaveBeenCalledWith(original);
    });
});
