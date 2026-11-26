import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn() } }));
vi.mock('../components/header/header', () => ({ default: () => null }));

import clienteAxios from '../components/auth/axiosConfig';
import HistorialPedidos from '../pages/HistorialPedidos';
import { leerTokensDeEnlace, olvidarTokensDeEnlace } from '../utils/enlacesConToken';

const pedido = (id, estado, extra = {}) => ({
  id, estado, fecha: '2026-10-20T12:00:00Z', total_final: 15000, detalles: [], token_resena: null,
  resena_enviada: false, ...extra
});

describe('Mis pedidos: reseñas', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clienteAxios.get.mockImplementation((url) => Promise.resolve({ data: url === 'ventas/mis-pedidos/' ? [
      pedido(12, 'ENTREGADO', { token_resena: 'abc:def/123' }),
      pedido(11, 'ENTREGADO', { resena_enviada: true }),
      pedido(10, 'ENVIADO')
    ] : {} }));
  });

  afterEach(() => cleanup());

  it('un pedido que se puede reseñar lleva al formulario con su enlace firmado, sin dejarlo en la URL', async () => {
    render(<MemoryRouter><HistorialPedidos /></MemoryRouter>);

    const enlace = await screen.findByRole('link', { name: 'Dejar reseña del pedido #12' });
    expect(enlace).toHaveAttribute('href', '/resena');
    fireEvent.click(enlace);
    expect(leerTokensDeEnlace('/resena')).toEqual({ t: 'abc:def/123' });
    olvidarTokensDeEnlace('/resena');
  });

  it('un pedido ya reseñado lo dice y uno en camino no ofrece nada', async () => {
    render(<MemoryRouter><HistorialPedidos /></MemoryRouter>);

    const fila = (await screen.findByText('#11')).closest('tr');
    expect(within(fila).getByText('Reseña enviada')).toBeInTheDocument();
    expect(within(fila).queryByRole('link', { name: /Dejar reseña/ })).not.toBeInTheDocument();
    const enCamino = screen.getByText('#10').closest('tr');
    expect(within(enCamino).queryByRole('link', { name: /Dejar reseña/ })).not.toBeInTheDocument();
    expect(within(enCamino).queryByText('Reseña enviada')).not.toBeInTheDocument();
  });
});

describe('Mis pedidos: foto de cada pedido', () => {
  const linea = (nombre, imagen, extra = {}) => ({
    producto_mongo_id: nombre, variante_sku: `${nombre}-1`, nombre_producto: nombre, precio_unitario: 5000,
    cantidad: 1, imagen, variante: '', ...extra,
  });

  function mostrar(pedidos) {
    clienteAxios.get.mockImplementation((url) => Promise.resolve({ data: url === 'ventas/mis-pedidos/' ? pedidos : {} }));
    render(<MemoryRouter><HistorialPedidos /></MemoryRouter>);
  }

  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it('la miniatura es la foto del primer producto, con "+2" si hay más', async () => {
    mostrar([pedido(7, 'ENTREGADO', { detalles: [
      linea('Polerón', 'https://cdn.test/poleron.jpg'), linea('Gorro', 'https://cdn.test/gorro.jpg'), linea('Taza', null),
    ] })]);

    const miniatura = await screen.findByRole('button', { name: 'Ver las fotos del pedido #7, 3 productos' });

    expect(miniatura.querySelector('img')).toHaveAttribute('src', 'https://cdn.test/poleron.jpg');
    expect(miniatura).toHaveTextContent('+2');
  });

  it('el visor recorre los productos con los botones y las flechas, y un producto sin foto lo dice', async () => {
    mostrar([pedido(7, 'ENTREGADO', { detalles: [
      linea('Polerón', 'https://cdn.test/poleron.jpg', { variante: 'Talla: M', cantidad: 2 }), linea('Taza', null),
    ] })]);
    fireEvent.click(await screen.findByRole('button', { name: /Ver las fotos del pedido #7/ }));

    const visor = screen.getByRole('dialog', { name: 'Pedido #7' });
    expect(within(visor).getByRole('img', { name: 'Polerón' })).toHaveAttribute('src', 'https://cdn.test/poleron.jpg');
    expect(visor).toHaveTextContent('Talla: M');
    expect(visor).toHaveTextContent('2 unidades');
    expect(visor).toHaveTextContent('1 de 2');

    fireEvent.click(within(visor).getByRole('button', { name: /Siguiente/ }));
    expect(visor).toHaveTextContent('Taza');
    expect(visor).toHaveTextContent('Este producto ya no tiene foto en la tienda.');
    expect(visor).toHaveTextContent('2 de 2');

    fireEvent.keyDown(within(visor).getByRole('heading', { name: 'Pedido #7' }), { key: 'ArrowRight' });
    expect(visor).toHaveTextContent('1 de 2');
    fireEvent.keyDown(within(visor).getByRole('heading', { name: 'Pedido #7' }), { key: 'ArrowLeft' });
    expect(visor).toHaveTextContent('2 de 2');
  });

  it('al cerrar el visor el foco vuelve a la miniatura', async () => {
    mostrar([pedido(7, 'ENTREGADO', { detalles: [linea('Polerón', 'https://cdn.test/poleron.jpg')] })]);
    const miniatura = await screen.findByRole('button', { name: 'Ver las fotos del pedido #7, 1 producto' });
    miniatura.focus();
    fireEvent.click(miniatura);

    const visor = screen.getByRole('dialog', { name: 'Pedido #7' });
    // Con un solo producto no hay "Anterior" ni "Siguiente"
    expect(within(visor).queryByRole('button', { name: /Siguiente/ })).not.toBeInTheDocument();
    fireEvent(visor, new Event('cancel', { cancelable: true }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(miniatura).toHaveFocus();
  });

  it('sin ninguna foto se ve el ícono, sin nada que abrir', async () => {
    mostrar([pedido(7, 'ENTREGADO', { detalles: [linea('Taza', null)] })]);

    expect(await screen.findByText('#7', { exact: false })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Ver las fotos/ })).not.toBeInTheDocument();
    expect(document.querySelector('.pedido-miniatura--vacia')).toBeInTheDocument();
  });
});
