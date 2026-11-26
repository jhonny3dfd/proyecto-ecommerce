import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import useConfiguracionTienda from '../hooks/useConfiguracionTienda';
import { obtenerEtiquetaProducto } from '../utils/etiquetasProducto';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));
vi.mock('../components/auth/AuthLayout', () => ({ default: ({ children }) => <main>{children}</main> }));
vi.mock('../hooks/useConfiguracionTienda', () => ({ default: vi.fn() }));
import clienteAxios from '../components/auth/axiosConfig';
import CampoExclusivoProducto from '../components/CampoExclusivoProducto';
import AccesoProductoExclusivo from '../components/AccesoProductoExclusivo';
import EtiquetaProducto from '../components/EtiquetaProducto';
import MiCumpleanos from '../pages/MiCumpleanos';
import GestorCumpleanos from '../components/GestorCumpleanos';
import { ajustarCarrito } from '../components/carrito';

const exclusivo = { id: 'producto', solo_suscriptores: true, planes_suscripcion: [2], variantes: [{ stock: 5, precio: 1000 }] };
const fila = { usuario_id: 7, nombre: 'Ana Prueba', dia: 29, mes: 2, direccion: 'Calle de ejemplo 202',
  direccion_envio: { calle: 'Calle de ejemplo', numero: '202', dpto_casa: 'Depto. 4', comuna: 'Santiago' },
  proxima_entrega: '2026-12-01', plan: 'Mensual', regalo_enviado: false };

beforeEach(() => { vi.resetAllMocks(); localStorage.clear(); useConfiguracionTienda.mockReturnValue({ suscripciones_activas: true }); });
afterEach(() => cleanup());

function Campo() {
  const [datos, setDatos] = useState({ solo_suscriptores: false, planes_suscripcion: [] });
  return <CampoExclusivoProducto activo exclusivo={datos.solo_suscriptores} planes={datos.planes_suscripcion}
    onChange={cambios => setDatos(d => ({ ...d, ...cambios }))} />;
}

describe('Productos exclusivos', () => {
  it('Agotado tiene prioridad sobre el exclusivo y vuelve a exclusivo al reponer stock', () => {
    expect(obtenerEtiquetaProducto({ ...exclusivo, variantes: [{ stock: 0, precio: 1000 }] }).texto).toBe('Agotado');
    expect(obtenerEtiquetaProducto(exclusivo).texto).toBe('Exclusivo suscriptores');
  });
  it('sin módulo no aparece la casilla ni consulta planes', () => {
    render(<CampoExclusivoProducto activo={false} planes={[]} />);
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(clienteAxios.get).not.toHaveBeenCalled();
  });

  it('permite activar la restricción y elegir planes mediante casillas con nombre', async () => {
    clienteAxios.get.mockResolvedValue({ data: { planes: [{ id: 2, nombre: 'Mensual', activo: true }] } });
    render(<Campo />);
    fireEvent.click(screen.getByLabelText('Solo para suscriptores'));
    const plan = await screen.findByRole('checkbox', { name: 'Mensual' });
    fireEvent.click(plan);
    expect(plan).toBeChecked();
    fireEvent.click(plan);
    expect(plan).not.toBeChecked();
    expect(screen.getByRole('group', { name: 'Planes permitidos' })).toBeInTheDocument();
  });

  it('al invitado le muestra el aviso y el enlace, sin controles de compra', () => {
    render(<MemoryRouter><AccesoProductoExclusivo producto={exclusivo}><button>Comprar</button></AccesoProductoExclusivo></MemoryRouter>);
    expect(screen.queryByRole('button', { name: 'Comprar' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Ver planes/ })).toHaveAttribute('href', '/suscripcion');
    expect(clienteAxios.get).not.toHaveBeenCalled();
  });

  it('un plan permitido deja comprar y otro plan no', async () => {
    localStorage.setItem('access_token', 'sesion-simulada');
    clienteAxios.get.mockResolvedValue({ data: { planes_vigentes: [2] } });
    const { rerender } = render(<MemoryRouter><AccesoProductoExclusivo producto={exclusivo}><button>Comprar</button></AccesoProductoExclusivo></MemoryRouter>);
    expect(await screen.findByRole('button', { name: 'Comprar' })).toBeInTheDocument();
    rerender(<MemoryRouter><AccesoProductoExclusivo producto={{ ...exclusivo, planes_suscripcion: [3] }}><button>Comprar</button></AccesoProductoExclusivo></MemoryRouter>);
    expect(screen.queryByRole('button', { name: 'Comprar' })).not.toBeInTheDocument();
  });

  it('un fallo de acceso no habilita la compra y se puede reintentar', async () => {
    localStorage.setItem('access_token', 'sesion-simulada');
    clienteAxios.get.mockRejectedValueOnce(new Error('Fallo controlado'))
      .mockResolvedValue({ data: { planes_vigentes: [2] } });
    render(<MemoryRouter><AccesoProductoExclusivo producto={exclusivo}><button>Comprar</button></AccesoProductoExclusivo></MemoryRouter>);
    expect(await screen.findByRole('alert')).toHaveTextContent('No pudimos comprobar');
    expect(screen.queryByText('Comprar')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByRole('button', { name: 'Comprar' })).toBeInTheDocument();
  });

  it('la etiqueta de exclusivo también aparece en la ficha sin etiqueta propia', () => {
    render(<EtiquetaProducto producto={exclusivo} enFicha />);
    expect(screen.getByText('Exclusivo suscriptores')).toBeInTheDocument();
  });

  it('retira del carrito una línea que perdió acceso', () => {
    const revision = { items: [{ producto_mongo_id: 'p', variante_sku: 'SKU',
      problema: 'SUSCRIPCION_REQUERIDA', mensaje: 'Necesitas una suscripción vigente.' }] };
    const resultado = ajustarCarrito([{ id: 'p', sku: 'SKU', cantidad: 1, precio: 1000 }], revision);
    expect(resultado.items).toEqual([]);
    expect(resultado.avisos[0]).toContain('Necesitas una suscripción vigente');
  });
});

describe('Mi cumpleaños', () => {
  it('con el módulo apagado vuelve al inicio sin consultar la fecha privada', async () => {
    useConfiguracionTienda.mockReturnValue({ suscripciones_activas: false });
    render(<MemoryRouter initialEntries={['/mi-cumpleanos']}><Routes>
      <Route path="/mi-cumpleanos" element={<MiCumpleanos />} />
      <Route path="/" element={<h1>Inicio</h1>} />
    </Routes></MemoryRouter>);
    expect(await screen.findByRole('heading', { name: 'Inicio' })).toBeInTheDocument();
    expect(clienteAxios.get).not.toHaveBeenCalled();
  });
  it('guarda día y mes sin año y permite eliminar ambos', async () => {
    clienteAxios.get.mockResolvedValue({ data: { dia: null, mes: null } });
    clienteAxios.patch.mockImplementation((_, datos) => Promise.resolve({ data: datos }));
    render(<MiCumpleanos />);
    fireEvent.change(await screen.findByLabelText('Día'), { target: { value: '29' } });
    fireEvent.change(screen.getByLabelText('Mes'), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cumpleaños' }));
    expect(await screen.findByRole('status')).toHaveTextContent('quedó guardado');
    expect(clienteAxios.patch).toHaveBeenCalledWith('usuarios/cumpleanos/', { dia: 29, mes: 2 });
    fireEvent.click(screen.getByRole('button', { name: 'Eliminar cumpleaños' }));
    expect(await screen.findByText('Tu cumpleaños se eliminó.')).toBeInTheDocument();
    expect(clienteAxios.patch).toHaveBeenLastCalledWith('usuarios/cumpleanos/', { dia: null, mes: null });
  });

  it('asocia el error de fecha a ambos campos y conserva los valores escritos', async () => {
    clienteAxios.get.mockResolvedValue({ data: { dia: 31, mes: 4 } });
    clienteAxios.patch.mockRejectedValue({ response: { data: { dia: ['La fecha no existe.'] } } });
    render(<MiCumpleanos />);
    await screen.findByLabelText('Día');
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cumpleaños' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('La fecha no existe.');
    expect(screen.getByLabelText('Día')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText('Mes')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText('Día')).toHaveValue(31);
  });
});

describe('Cumpleaños del mes en el panel', () => {
  beforeEach(() => {
    clienteAxios.get.mockResolvedValue({ data: { count: 1, results: [fila], anio: 2026, next: null } });
  });

  it('marcar un regalo no marca a otra persona del listado', async () => {
    clienteAxios.get.mockResolvedValue({ data: { count: 2, results: [fila,
      { ...fila, usuario_id: 8, nombre: 'Beto Prueba' }], anio: 2026, next: null } });
    clienteAxios.post.mockResolvedValue({ data: { regalo_enviado: true, anio: 2026 } });
    render(<GestorCumpleanos />);
    const ana = await screen.findByRole('checkbox', { name: 'Regalo enviado a Ana Prueba en 2026' });
    const beto = screen.getByRole('checkbox', { name: 'Regalo enviado a Beto Prueba en 2026' });
    fireEvent.click(beto);
    await waitFor(() => expect(beto).toBeChecked());
    expect(ana).not.toBeChecked();
    expect(ana).toBeEnabled();
    expect(clienteAxios.post).toHaveBeenCalledExactlyOnceWith('ventas/admin/suscripciones/cumpleanos/8/regalo/');
  });

  it('muestra dirección completa y entrega; registra una sola vez y deshabilita la casilla', async () => {
    clienteAxios.post.mockResolvedValue({ data: { regalo_enviado: true, anio: 2026 } });
    render(<GestorCumpleanos />);
    const casilla = await screen.findByRole('checkbox', { name: 'Regalo enviado a Ana Prueba en 2026' });
    expect(screen.getByText(/Depto. 4/)).toBeInTheDocument();
    expect(screen.getByText('1 de diciembre de 2026')).toBeInTheDocument();
    fireEvent.click(casilla);
    await waitFor(() => expect(casilla).toBeChecked());
    expect(casilla).toBeDisabled();
    expect(clienteAxios.post).toHaveBeenCalledTimes(1);
  });

  it('un error no marca el regalo y permite volver a intentarlo', async () => {
    clienteAxios.post.mockRejectedValue(new Error('Fallo controlado'));
    render(<GestorCumpleanos />);
    const casilla = await screen.findByRole('checkbox', { name: /Regalo enviado a Ana/ });
    fireEvent.click(casilla);
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo registrar');
    expect(casilla).not.toBeChecked();
    expect(casilla).not.toBeDisabled();
  });

  it('cambia el mes consultando el servidor y reinicia la página', async () => {
    render(<GestorCumpleanos />);
    await screen.findByText('Ana Prueba');
    fireEvent.change(screen.getByLabelText('Mes de cumpleaños'), { target: { value: '2' } });
    await waitFor(() => expect(clienteAxios.get).toHaveBeenLastCalledWith('ventas/admin/suscripciones/cumpleanos/',
      { params: { mes: 2, pagina: 1 } }));
  });
});
