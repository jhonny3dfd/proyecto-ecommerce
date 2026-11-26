import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), patch: vi.fn() } }));
vi.mock('../hooks/useConfiguracionTienda', () => ({ recargarConfiguracion: vi.fn() }));

import clienteAxios from '../components/auth/axiosConfig';
import { recargarConfiguracion } from '../hooks/useConfiguracionTienda';
import Estrellas from '../components/Estrellas';
import GestorActivarResenas from '../components/GestorActivarResenas';
import GestorResenas from '../components/GestorResenas';

const resena = (id, estado = 'PENDIENTE') => ({
  id, orden_id: 100 + id, estado, estado_display: { PENDIENTE: 'Pendiente', APROBADA: 'Aprobada', OCULTA: 'Oculta' }[estado],
  fecha_creacion: '2026-10-25T12:00:00Z', estrellas: 4, comentario: 'Muy buena atención', nombre_publico: `Cliente ${id}`,
  productos: [{ producto_mongo_id: 'taza', producto_nombre: 'Taza de cerámica', estrellas: 5, comentario: 'Linda' }]
});

describe('Estrellas', () => {
  afterEach(() => cleanup());

  it('se leen como texto y dibujan el promedio redondeado', () => {
    const { container } = render(<Estrellas valor={4.5} />);
    expect(screen.getByRole('img', { name: '4,5 de 5 estrellas' })).toBeInTheDocument();
    expect(container.querySelectorAll('.estrella--llena')).toHaveLength(5);
    cleanup();
    const { container: otra } = render(<Estrellas valor={3} />);
    expect(screen.getByRole('img', { name: '3 de 5 estrellas' })).toBeInTheDocument();
    expect(otra.querySelectorAll('.estrella--llena')).toHaveLength(3);
  });
});

describe('GestorActivarResenas', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clienteAxios.get.mockResolvedValue({ data: { resenas_activas: false } });
  });

  afterEach(() => cleanup());

  it('parte apagado y el admin las activa', async () => {
    clienteAxios.patch.mockImplementation((_, datos) => Promise.resolve({ data: datos }));
    render(<GestorActivarResenas />);

    const casilla = await screen.findByRole('checkbox', { name: /pedir reseñas a mis clientes/i });
    expect(casilla).not.toBeChecked();
    fireEvent.click(casilla);
    fireEvent.click(screen.getByRole('button', { name: 'Guardar reseñas' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Reseñas activadas');
    expect(clienteAxios.patch).toHaveBeenCalledWith('configuracion/negocio/', { resenas_activas: true });
    expect(recargarConfiguracion).toHaveBeenCalled();
  });

  it('si no se puede guardar lo avisa', async () => {
    clienteAxios.patch.mockRejectedValue(new Error('500'));
    render(<GestorActivarResenas />);

    fireEvent.click(await screen.findByRole('button', { name: 'Guardar reseñas' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudieron guardar');
  });
});

describe('GestorResenas', () => {
  beforeEach(() => vi.clearAllMocks());

  afterEach(() => cleanup());

  it('muestra las pendientes con sus estrellas y deja aprobarlas', async () => {
    let pendientes = [resena(1), resena(2)];
    clienteAxios.get.mockImplementation((_, { params }) => Promise.resolve({ data: params.estado === 'PENDIENTE'
      ? { count: pendientes.length, results: pendientes } : { count: 0, results: [] } }));
    clienteAxios.patch.mockImplementation((url, { estado }) => {
      pendientes = pendientes.filter(r => !url.endsWith(`/${r.id}/`));
      return Promise.resolve({ data: { ...resena(1), estado } });
    });
    render(<GestorResenas />);

    const tarjeta = (await screen.findByRole('heading', { name: 'Cliente 1 · Pedido #101' })).closest('article');
    expect(clienteAxios.get).toHaveBeenCalledWith('ventas/admin/resenas/', { params: { estado: 'PENDIENTE', pagina: 1 } });
    expect(within(tarjeta).getByRole('img', { name: '4 de 5 estrellas' })).toBeInTheDocument();
    expect(within(tarjeta).getByText('Taza de cerámica')).toBeInTheDocument();
    expect(within(tarjeta).getByRole('img', { name: '5 de 5 estrellas' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pendientes' })).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(within(tarjeta).getByRole('button', { name: 'Aprobar la reseña de Cliente 1' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Publicaste la reseña de Cliente 1');
    expect(clienteAxios.patch).toHaveBeenCalledWith('ventas/admin/resenas/1/', { estado: 'APROBADA' });
    expect(await screen.findByRole('heading', { name: 'Cliente 2 · Pedido #102' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', {name: 'Cliente 1 · Pedido #101'})).not.toBeInTheDocument();
  });

  it('cambia de pestaña y una aprobada solo se puede ocultar', async () => {
    clienteAxios.get.mockImplementation((_, { params }) => Promise.resolve({ data: params.estado === 'APROBADA'
      ? { count: 1, results: [resena(3, 'APROBADA')] } : { count: 0, results: [] } }));
    render(<GestorResenas />);

    expect(await screen.findByText('No hay reseñas por revisar.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Aprobadas' }));

    const tarjeta = (await screen.findByRole('heading', { name: 'Cliente 3 · Pedido #103' })).closest('article');
    expect(within(tarjeta).queryByRole('button', { name: /Aprobar/ })).not.toBeInTheDocument();
    expect(within(tarjeta).getByRole('button', { name: 'Ocultar la reseña de Cliente 3' })).toBeInTheDocument();
    expect(clienteAxios.get).toHaveBeenLastCalledWith('ventas/admin/resenas/', { params: { estado: 'APROBADA', pagina: 1 } });
  });

  it('muestra el motivo si el servidor rechaza la moderación', async () => {
    clienteAxios.get.mockResolvedValue({ data: { count: 1, results: [resena(4)] } });
    clienteAxios.patch.mockRejectedValue({ response: { data: { estado: ['Una reseña oculta no puede quedar como pendiente.'] } } });
    render(<GestorResenas />);

    fireEvent.click(await screen.findByRole('button', { name: 'Ocultar la reseña de Cliente 4' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('no puede quedar como pendiente');
  });

  it('pagina de a 20', async () => {
    clienteAxios.get.mockImplementation((_, { params }) => Promise.resolve({ data: {
      count: 25, results: [resena(params.pagina === 1 ? 1 : 21)]
    } }));
    render(<GestorResenas />);

    expect(await screen.findByText('Página 1 de 2')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Siguientes/ }));

    expect(await screen.findByRole('heading', { name: 'Cliente 21 · Pedido #121' })).toBeInTheDocument();
    expect(screen.getByText('Página 2 de 2')).toBeInTheDocument();
  });

  it('al moderar la única reseña de la última página vuelve a la anterior', async () => {
    let total = 21;
    clienteAxios.get.mockImplementation((_, { params }) => params.pagina > Math.ceil(total / 20)
      // Como DRF: una página que no existe responde 404
      ? Promise.reject({ response: { status: 404 } })
      : Promise.resolve({ data: { count: total, results: [resena(params.pagina === 1 ? 1 : 21)] } }));
    clienteAxios.patch.mockImplementation(() => {
      total = 20;
      return Promise.resolve({ data: { ...resena(21), estado: 'APROBADA' } });
    });
    render(<GestorResenas />);

    fireEvent.click(await screen.findByRole('button', { name: /Siguientes/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Aprobar la reseña de Cliente 21' }));

    expect(await screen.findByRole('heading', { name: 'Cliente 1 · Pedido #101' })).toBeInTheDocument();
    expect(clienteAxios.get).toHaveBeenLastCalledWith('ventas/admin/resenas/', { params: { estado: 'PENDIENTE', pagina: 1 } });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
