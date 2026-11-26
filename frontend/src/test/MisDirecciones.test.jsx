import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import MisDirecciones from '../components/MisDirecciones';
import clienteAxios from '../components/auth/axiosConfig';
import { aplicarPaleta } from '../constants/palettes';
import { useNavigate } from 'react-router-dom';

vi.mock('react-router-dom', async (importOriginal) => {
    const actual = await importOriginal();
    return {
        ...actual,
        useNavigate: vi.fn()
    };
});

vi.mock('../components/auth/axiosConfig', () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn()
    }
}));

//Mocks de componentes externos: Header, palettes, etc
vi.mock('../components/header/header', () => ({
    default: () => <header>Header de prueba</header>
}));

vi.mock('../constants/palettes', () => ({
    aplicarPaleta: vi.fn()
}));

vi.mock('../components/carga/Esqueleto', () => ({
    Cargando: ({ texto, children }) => (
        <div>
            <p>{texto}</p>
            {children}
        </div>
    )
}));

vi.mock('../components/carga/EsqueletosPanel', () => ({
    EsqueletoLista: ({ elementos }) => (
        <div data-testid="esqueleto-lista">{elementos}</div>
    )
}));

const direccionesEjemplo = [
    {
        id: 1,
        calle: 'Av. Providencia',
        calle_numero: '1234',
        dpto_casa: 'Depto 505',
        comuna: 'Providencia',
        ciudad: 'Santiago',
        region: 'Metropolitana',
        es_predeterminado: true
    },
    {
        id: 2,
        calle: 'Av. Grecia',
        calle_numero: '456',
        dpto_casa: '',
        comuna: 'Ñuñoa',
        ciudad: 'Santiago',
        region: '',
        es_predeterminado: false
    }
];

const prepararRespuestas = ({
    direcciones = direccionesEjemplo,
    configuracion = { tema_seleccionado: 2 },
    comunas = ['Providencia', 'Ñuñoa', 'Puente Alto']
} = {}) => {
    clienteAxios.get.mockImplementation((url) => {
        if (url === 'ventas/direcciones/') {
            return Promise.resolve({ data: direcciones });
        }

        if (url === 'configuracion/') {
            return Promise.resolve({ data: configuracion });
        }

        if (url === 'ventas/logistica/comunas/') {
            return Promise.resolve({ data: { comunas } });
        }

        return Promise.reject(new Error('URL no reconocida'));
    });
};

const renderComponente = () => render(<MisDirecciones />);

describe('MisDirecciones', () => {
    beforeEach(() => {
        localStorage.clear();
        vi.clearAllMocks();

        prepararRespuestas();

        useNavigate.mockReturnValue(vi.fn());
    });

    afterEach(() => {
        cleanup();
        vi.restoreAllMocks();
    });

    it('muestra las direcciones existentes', async () => {
        renderComponente();

        expect(await screen.findByText('Av. Providencia 1234 - Depto 505'))
            .toBeInTheDocument();

        expect(screen.getByText('Av. Grecia 456')).toBeInTheDocument();
        expect(screen.getByText('Providencia, Santiago')).toBeInTheDocument();
    });

    it('identifica la dirección principal', async () => {
        renderComponente();

        expect(await screen.findByText('Principal')).toBeInTheDocument();

        expect(screen.getByText('Hacer principal')).toBeInTheDocument();
    });

    it('muestra un mensaje cuando no existen direcciones', async () => {
        prepararRespuestas({ direcciones: [] });

        renderComponente();

        expect(
            await screen.findByText('Aún no tienes direcciones guardadas.')
        ).toBeInTheDocument();

        expect(
            screen.getByRole('button', { name: 'Agregar mi primera dirección' })
        ).toBeInTheDocument();
    });

    it('muestra un error cuando falla la carga de direcciones', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});

        clienteAxios.get.mockImplementation((url) => {
            if (url === 'ventas/direcciones/') {
                return Promise.reject(new Error('Error de servidor'));
            }

            if (url === 'configuracion/') {
                return Promise.resolve({ data: {} });
            }

            return Promise.resolve({ data: { comunas: [] } });
        });

        renderComponente();

        expect(
            await screen.findByRole('alert')
        ).toHaveTextContent(
            'No se pudieron cargar tus direcciones. Intenta de nuevo.'
        );
    });-

    it('aplica el tema recibido desde la configuración', async () => {
        prepararRespuestas({
            configuracion: { tema_seleccionado: 3 }
        });

        renderComponente();

        await waitFor(() => {
            expect(aplicarPaleta).toHaveBeenCalledWith(3);
        });

        expect(localStorage.getItem('ecommerce_palette')).toBe('3');
    });

    it('carga las comunas disponibles en el formulario', async () => {
        renderComponente();

        fireEvent.click(
            screen.getByRole('button', { name: '+ Nueva dirección' })
        );

        expect(
            await screen.findByRole('option', { name: 'Puente Alto' })
        ).toBeInTheDocument();
    });

    it('permite abrir y cancelar el formulario', async () => {
        renderComponente();

        fireEvent.click(
            screen.getByRole('button', { name: '+ Nueva dirección' })
        );

        expect(
            screen.getByRole('heading', { name: 'Agregar nueva dirección' })
        ).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));

        expect(
            screen.queryByRole('heading', { name: 'Agregar nueva dirección' })
        ).not.toBeInTheDocument();
    });

    it('crea una nueva dirección correctamente', async () => {
        clienteAxios.post.mockResolvedValue({ data: {} });

        renderComponente();

        fireEvent.click(
            screen.getByRole('button', { name: '+ Nueva dirección' })
        );

        await screen.findByRole('option', { name: 'Puente Alto' });

        fireEvent.change(screen.getByLabelText('Calle'), {
            target: { value: 'Av. Vicuña Mackenna' }
        });

        fireEvent.change(screen.getByLabelText('Número'), {
            target: { value: '1000' }
        });

        fireEvent.change(
            screen.getByLabelText('Dpto, casa o referencia (opcional)'),
            { target: { value: 'Casa 12' } }
        );

        fireEvent.change(screen.getByLabelText('Comuna'), {
            target: { value: 'Puente Alto' }
        });

        fireEvent.change(screen.getByLabelText('Ciudad'), {
            target: { value: 'Santiago' }
        });

        fireEvent.change(screen.getByLabelText('Región (opcional)'), {
            target: { value: 'Metropolitana' }
        });

        fireEvent.click(
            screen.getByRole('checkbox', {
                name: 'Establecer como dirección principal'
            })
        );

        fireEvent.click(
            screen.getByRole('button', { name: 'Guardar dirección' })
        );

        await waitFor(() => {
            expect(clienteAxios.post).toHaveBeenCalledWith(
                'ventas/direcciones/',
                {
                    calle: 'Av. Vicuña Mackenna',
                    calle_numero: '1000',
                    dpto_casa: 'Casa 12',
                    comuna: 'Puente Alto',
                    ciudad: 'Santiago',
                    region: 'Metropolitana',
                    es_predeterminado: true
                }
            );
        });

        expect(await screen.findByRole('status'))
            .toHaveTextContent('Dirección guardada exitosamente.');
    });

    it('muestra un error cuando falla la creación de una dirección', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});

        clienteAxios.post.mockRejectedValue(new Error('Error de servidor'));

        renderComponente();

        fireEvent.click(
            screen.getByRole('button', { name: '+ Nueva dirección' })
        );

        fireEvent.change(screen.getByLabelText('Calle'), {
            target: { value: 'Av. Vicuña Mackenna' }
        });

        fireEvent.change(screen.getByLabelText('Número'), {
            target: { value: '1000' }
        });

        fireEvent.change(screen.getByLabelText('Comuna'), {
            target: { value: 'Puente Alto' }
        });

        fireEvent.change(screen.getByLabelText('Ciudad'), {
            target: { value: 'Santiago' }
        });

        fireEvent.click(
            screen.getByRole('button', { name: 'Guardar dirección' })
        );

        expect(await screen.findByRole('alert'))
            .toHaveTextContent(
                'Hubo un error al guardar la dirección. Verifica los datos.'
            );
    });

    it('permite establecer otra dirección como principal', async () => {
        renderComponente();

        fireEvent.click(
            await screen.findByRole('button', { name: 'Hacer principal' })
        );

        await waitFor(() => {
            expect(clienteAxios.patch).toHaveBeenCalledWith(
                'ventas/direcciones/2/',
                { es_predeterminado: true }
            );
        });

        expect(await screen.findByRole('status'))
            .toHaveTextContent('Dirección principal actualizada.');
    });

    it('muestra un error cuando falla la actualización de la dirección principal', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});

        clienteAxios.patch.mockRejectedValue(new Error('Error de servidor'));

        renderComponente();

        fireEvent.click(
            await screen.findByRole('button', { name: 'Hacer principal' })
        );

        expect(await screen.findByRole('alert'))
            .toHaveTextContent(
                'No se pudo actualizar la dirección principal.'
            );
    });

    it('no elimina la dirección si el usuario cancela la confirmación', async () => {
        vi.spyOn(window, 'confirm').mockReturnValue(false);

        renderComponente();

        fireEvent.click(
            (await screen.findAllByRole('button', { name: 'Eliminar' }))[0]
        );

        expect(window.confirm).toHaveBeenCalledWith(
            '¿Estás seguro de que deseas eliminar esta dirección?'
        );

        expect(clienteAxios.delete).not.toHaveBeenCalled();
    });

    it('elimina una dirección cuando el usuario confirma', async () => {
        vi.spyOn(window, 'confirm').mockReturnValue(true);

        clienteAxios.delete.mockResolvedValue({ data: {} });

        renderComponente();

        fireEvent.click(
            (await screen.findAllByRole('button', { name: 'Eliminar' }))[0]
        );

        await waitFor(() => {
            expect(clienteAxios.delete).toHaveBeenCalledWith(
                'ventas/direcciones/1/'
            );
        });

        expect(await screen.findByRole('status'))
            .toHaveTextContent('Dirección eliminada correctamente.');
    });

    it('muestra un error cuando falla la eliminación', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});
        vi.spyOn(window, 'confirm').mockReturnValue(true);

        clienteAxios.delete.mockRejectedValue(new Error('Error de servidor'));

        renderComponente();

        fireEvent.click(
            (await screen.findAllByRole('button', { name: 'Eliminar' }))[0]
        );

        expect(await screen.findByRole('alert'))
            .toHaveTextContent('No se pudo eliminar la dirección.');
    });

    it('permite volver al catálogo', async () => {
        const navegar = vi.fn();
        useNavigate.mockReturnValue(navegar);

        renderComponente();

        fireEvent.click(
            screen.getByRole('button', { name: /Volver a la tienda/ })
        );

        expect(navegar).toHaveBeenCalledWith('/catalogo');
    });
});
