import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const { configuracion } = vi.hoisted(() => ({ configuracion: { actual: null } }));

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), patch: vi.fn() } }));
vi.mock('../hooks/useConfiguracionTienda', () => ({
  default: () => configuracion.actual,
  recargarConfiguracion: vi.fn()
}));
vi.mock('../components/header/header', () => ({ default: () => null }));
vi.mock('../components/VariantSelector', () => ({ default: () => null }));
vi.mock('../components/carrito', () => ({ validarCarrito: vi.fn(), guardarCarrito: vi.fn() }));

import clienteAxios from '../components/auth/axiosConfig';
import LandingPage from '../pages/LandingPage';
import DetalleProducto from '../pages/DetalleProducto';

const RESENAS_TIENDA = {
  promedio: 4.5, total: 2,
  resenas: [{ nombre_publico: 'Ana P.', estrellas: 5, comentario: 'Llegó impecable', fecha: '2026-10-20T12:00:00Z' }]
};
const PRODUCTO = { id: 'taza', nombre: 'Taza de cerámica', imagenes: [], variantes: [{ sku: 'T-1', precio: 9000, stock: 2 }] };

function responder({ tienda = RESENAS_TIENDA, producto = { promedio: 4, total: 1, resenas: [
  { nombre_publico: 'Luis R.', estrellas: 4, comentario: 'Linda taza', fecha: '2026-10-21T12:00:00Z' }] } } = {}) {
  clienteAxios.get.mockImplementation((url) => {
    if (url === 'catalogo/vitrina/') return Promise.resolve({ data: { mas_vendidos: [], recientes: [] } });
    if (url === 'ventas/resenas/tienda/') return Promise.resolve({ data: tienda });
    if (url === 'catalogo/productos/taza/') return Promise.resolve({ data: PRODUCTO });
    if (url === 'ventas/resenas/producto/taza/') return Promise.resolve({ data: producto });
    return Promise.resolve({ data: [] });
  });
}

const renderLanding = () => render(<MemoryRouter><LandingPage /></MemoryRouter>);
const renderFicha = () => render(
  <MemoryRouter initialEntries={['/catalogo/producto/taza']}>
    <Routes><Route path="/catalogo/producto/:id" element={<DetalleProducto />} /></Routes>
  </MemoryRouter>
);

describe('Reseñas en la landing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    configuracion.actual = { nombre_tienda: 'Taller Maché', resenas_activas: true };
    responder();
  });

  afterEach(() => cleanup());

  it('muestra el promedio y las últimas aprobadas', async () => {
    renderLanding();

    const seccion = (await screen.findByRole('heading', { name: 'Lo que dicen nuestros clientes' })).closest('section');
    expect(seccion).toHaveTextContent('4,5 de 5 · 2 reseñas');
    expect(within(seccion).getByRole('img', { name: '5 de 5 estrellas' })).toBeInTheDocument();
    expect(within(seccion).getByText('Llegó impecable').closest('blockquote')).toBeInTheDocument();
    expect(within(seccion).getByText('Ana P.')).toBeInTheDocument();
    expect(within(seccion).getByText('octubre de 2026')).toBeInTheDocument();
  });

  it('sin reseñas aprobadas la sección no aparece', async () => {
    responder({ tienda: { promedio: null, total: 0, resenas: [] } });
    renderLanding();

    await vi.waitFor(() => expect(clienteAxios.get).toHaveBeenCalledWith('ventas/resenas/tienda/'));
    expect(screen.queryByRole('heading', { name: 'Lo que dicen nuestros clientes' })).not.toBeInTheDocument();
  });

  it('con las reseñas apagadas ni siquiera se consultan', async () => {
    configuracion.actual = { nombre_tienda: 'Taller Maché', resenas_activas: false };
    renderLanding();

    await vi.waitFor(() => expect(clienteAxios.get).toHaveBeenCalledWith('catalogo/vitrina/'));
    expect(clienteAxios.get).not.toHaveBeenCalledWith('ventas/resenas/tienda/');
    expect(screen.queryByRole('heading', { name: 'Lo que dicen nuestros clientes' })).not.toBeInTheDocument();
  });
});

describe('Reseñas en la ficha del producto', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    configuracion.actual = { nombre_tienda: 'Taller Maché', resenas_activas: true };
    responder();
  });

  afterEach(() => cleanup());

  it('muestra el promedio junto al nombre, con enlace a las reseñas', async () => {
    renderFicha();

    const enlace = await screen.findByRole('link', { name: '4,0 de 5 · 1 reseña' });
    expect(enlace).toHaveAttribute('href', '#resenas');
    const seccion = screen.getByRole('heading', { name: 'Reseñas' }).closest('section');
    expect(seccion).toHaveAttribute('id', 'resenas');
    expect(within(seccion).getByText('Linda taza')).toBeInTheDocument();
    expect(within(seccion).getByText('Luis R.')).toBeInTheDocument();
  });

  it('con calificaciones sin comentarios lo dice', async () => {
    responder({ producto: { promedio: 3, total: 2, resenas: [] } });
    renderFicha();

    expect(await screen.findByText(/todavía no dejan comentarios/)).toBeInTheDocument();
  });

  it('un producto sin reseñas aprobadas no muestra nada', async () => {
    responder({ producto: { promedio: null, total: 0, resenas: [] } });
    renderFicha();

    expect(await screen.findByRole('heading', { name: 'Taza de cerámica' })).toBeInTheDocument();
    await vi.waitFor(() => expect(clienteAxios.get).toHaveBeenCalledWith('ventas/resenas/producto/taza/'));
    expect(screen.queryByRole('heading', { name: 'Reseñas' })).not.toBeInTheDocument();
  });
});
