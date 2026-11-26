import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import PaginaLegal from '../pages/PaginaLegal';
import clienteAxios from '../components/auth/axiosConfig';

vi.mock('../components/auth/axiosConfig', () => ({
    default: {
        get: vi.fn()
    }
}));

vi.mock('../components/header/header', () => ({
    default: () => <header>Header</header>
}));

vi.mock('../components/carga/Esqueleto', () => ({
    Cargando: ({ texto, children }) => (
        <div>
            <span>{texto}</span>
            {children}
        </div>
    )
}));

vi.mock('../components/carga/EsqueletosTienda', () => ({
    EsqueletoTexto: () => <div>Esqueleto de texto</div>
}));

vi.mock('react-quill-new/dist/quill.snow.css', () => ({}));

const paginaEjemplo = {
    titulo: 'Términos de prueba',
    contenido: '<p>Contenido de términos</p>',
    ultima_actualizacion: '2026-10-01T12:00:00'
};

const renderPagina = (tipo = 'TERMINOS') => {
    return render(
        <MemoryRouter initialEntries={[`/legal/${tipo}`]}>
            <Routes>
                <Route
                    path="/legal/:tipo"
                    element={<PaginaLegal />}
                />
            </Routes>
        </MemoryRouter>
    );
};

describe('PaginaLegal', () => {

    beforeEach(() => {
        cleanup();
        vi.clearAllMocks();
        document.title = 'Tienda';
    });

    it('muestra el encabezado mientras carga la página', () => {
        clienteAxios.get.mockReturnValue(new Promise(() => {}));

        renderPagina();

        expect(screen.getByText('Header')).toBeInTheDocument();
        expect(screen.getByText('Cargando la página...')).toBeInTheDocument();
    });

    it('muestra el contenido de términos cuando la API responde correctamente', async () => {
        clienteAxios.get.mockResolvedValue({
            data: paginaEjemplo
        });

        renderPagina('TERMINOS');

        expect(
            await screen.findByRole('heading', {
                name: 'Términos de prueba'
            })
        ).toBeInTheDocument();

        expect(
            screen.getByText('Contenido de términos')
        ).toBeInTheDocument();
    });

    it('consulta la API utilizando el tipo de página de la URL', async () => {
        clienteAxios.get.mockResolvedValue({
            data: paginaEjemplo
        });

        renderPagina('PRIVACIDAD');

        await waitFor(() => {
            expect(clienteAxios.get).toHaveBeenCalledWith(
                'ventas/paginas-legales/PRIVACIDAD/'
            );
        });
    });

    it('muestra la fecha de última actualización', async () => {
        clienteAxios.get.mockResolvedValue({
            data: paginaEjemplo
        });

        renderPagina();

        const fecha = await screen.findByText(/Última actualización:/);
        expect(fecha).toBeInTheDocument();
    });

    it('actualiza el título del documento', async () => {
        clienteAxios.get.mockResolvedValue({
            data: paginaEjemplo
        });

        renderPagina();

        await waitFor(() => {
            expect(document.title).toBe('Términos de prueba');
        });
    });

    it('muestra página no encontrada cuando la API responde 404', async () => {
        clienteAxios.get.mockRejectedValue({
            response: {
                status: 404
            }
        });

        renderPagina('PRIVACIDAD');

        expect(
            await screen.findByRole('heading', {
                name: 'Página no encontrada'
            })
        ).toBeInTheDocument();

        expect(
            screen.getByText(
                'La página legal que buscas no existe o aún no está publicada.'
            )
        ).toBeInTheDocument();
    });

    it('muestra un mensaje cuando ocurre un error de conexión', async () => {
        clienteAxios.get.mockRejectedValue(
            new Error('Error de conexión')
        );

        renderPagina();

        expect(
            await screen.findByRole('heading', {
                name: 'No pudimos cargar esta página'
            })
        ).toBeInTheDocument();

        expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('muestra el enlace para volver al catálogo', async () => {
        clienteAxios.get.mockRejectedValue({
            response: {
                status: 404
            }
        });

        renderPagina();

        const enlace = await screen.findByRole('link', {name: 'Ir al catálogo'});
        expect(enlace).toHaveAttribute('href', '/catalogo');
    });
});
