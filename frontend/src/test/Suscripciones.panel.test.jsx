import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';

vi.mock('../components/auth/axiosConfig', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() }
}));
vi.mock('../hooks/useConfiguracionTienda', () => ({ default: vi.fn(() => null), recargarConfiguracion: vi.fn() }));

import clienteAxios from '../components/auth/axiosConfig';
import useConfiguracionTienda, { recargarConfiguracion } from '../hooks/useConfiguracionTienda';
import AdminSidebar from '../components/AdminSidebar';
import GestorSuscripciones from '../components/GestorSuscripciones';
import GestorSuscriptores from '../components/GestorSuscriptores';

// Suscripciones (pedido de un cliente, opcional): el panel

const plan = (cambios = {}) => ({
  id: 1, nombre: 'Café del mes', descripcion: '', precio: 15990, frecuencia_semanas: 4, frecuencia_texto: 'Cada 4 semanas',
  unidades: 1, beneficios: [], categorias: ['Café en grano'], productos: [], envio_gratis: false,
  envio_gratis_compras: false, descuento: 0, activo: true, orden: 1, suscripciones: 0, ...cambios
});

const PRODUCTOS = [
  { id: 'p1', nombre: 'Etiopía Yirgacheffe', categoria: 'Café en grano' },
  { id: 'p2', nombre: 'Taza de cerámica', categoria: 'Accesorios' }
];

const responder = ({ config = {}, planes = [plan()] } = {}) => {
  clienteAxios.get.mockImplementation((url) => {
    if (url === 'configuracion/negocio/') {
      return Promise.resolve({ data: { suscripciones_activas: false, suscripciones_dias_aviso: 3, ...config } });
    }
    if (url === 'ventas/admin/suscripciones/planes/') return Promise.resolve({ data: { planes } });
    if (url.startsWith('catalogo/productos/')) return Promise.resolve({ data: PRODUCTOS });
    return Promise.reject(new Error(`URL inesperada: ${url}`));
  });
};

describe('GestorSuscripciones (Configuración > Suscripciones)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    responder();
  });

  afterEach(() => cleanup());

  it('parte apagado y el admin lo activa con sus días de aviso', async () => {
    clienteAxios.patch.mockImplementation((_, datos) => Promise.resolve({ data: datos }));
    render(<GestorSuscripciones />);

    const casilla = await screen.findByRole('checkbox', { name: 'Ofrecer suscripciones en mi tienda' });
    expect(casilla).not.toBeChecked();
    fireEvent.click(casilla);
    fireEvent.change(screen.getByLabelText('Días de anticipación de cada pedido'), { target: { value: '5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar suscripciones' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Suscripciones activadas');
    expect(clienteAxios.patch).toHaveBeenCalledWith('configuracion/negocio/',
      { suscripciones_activas: true, suscripciones_dias_aviso: 5 });
    expect(recargarConfiguracion).toHaveBeenCalled();
  });

  it('muestra el error del servidor junto a los días de aviso', async () => {
    clienteAxios.patch.mockRejectedValue({ response: { data: { suscripciones_dias_aviso: ['Debe estar entre 1 y 14 días.'] } } });
    render(<GestorSuscripciones />);

    const dias = await screen.findByLabelText('Días de anticipación de cada pedido');
    fireEvent.change(dias, { target: { value: '7' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar suscripciones' }));

    expect(await screen.findByText('Debe estar entre 1 y 14 días.')).toBeInTheDocument();
    expect(dias).toHaveAttribute('aria-invalid', 'true');
    expect(dias.getAttribute('aria-describedby')).toContain('suscripciones-dias-aviso-error');
  });

  it('sin planes disponibles avisa que la página se verá vacía', async () => {
    responder({ planes: [plan({ activo: false })] });
    render(<GestorSuscripciones />);

    expect(await screen.findByText(/crea al menos un plan disponible/i)).toBeInTheDocument();
    expect(screen.getByText('No disponible')).toBeInTheDocument();
  });

  it('crea un plan con beneficios uno por línea, categorías y productos', async () => {
    responder({ planes: [] });
    clienteAxios.post.mockImplementation((_, datos) => Promise.resolve({ data: { id: 9, ...datos, frecuencia_texto: 'Cada 2 semanas', orden: 1 } }));
    render(<GestorSuscripciones />);

    fireEvent.click(await screen.findByRole('button', { name: '+ Nuevo plan' }));
    fireEvent.change(screen.getByLabelText('Nombre del plan'), { target: { value: 'Café quincenal' } });
    fireEvent.change(screen.getByLabelText('Precio por entrega ($)'), { target: { value: '12990' } });
    fireEvent.change(screen.getByLabelText('Cada cuánto llega'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('Unidades por entrega'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText(/Beneficios/), { target: { value: 'Recién tostado\n\n  Guía de preparación  ' } });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Café en grano' }));
    fireEvent.click(screen.getByRole('checkbox', { name: /Taza de cerámica/ }));
    fireEvent.change(screen.getByLabelText(/Descuento en sus otras compras/), { target: { value: '10' } });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Envío gratis en las entregas de la suscripción' }));
    fireEvent.click(screen.getByRole('button', { name: 'Crear plan' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Creaste el plan "Café quincenal".');
    expect(clienteAxios.post).toHaveBeenCalledWith('ventas/admin/suscripciones/planes/', expect.objectContaining({
      nombre: 'Café quincenal', precio: 12990, frecuencia_semanas: 2, unidades: 2, descuento: 10,
      beneficios: ['Recién tostado', 'Guía de preparación'], categorias: ['Café en grano'], productos: ['p2'],
      envio_gratis: true, envio_gratis_compras: false, activo: true
    }));
    expect(screen.getByRole('heading', { name: 'Café quincenal' })).toBeInTheDocument();
  });

  it('el envío gratis en todas las compras exige el de la suscripción', async () => {
    render(<GestorSuscripciones />);

    fireEvent.click(await screen.findByRole('button', { name: 'Editar Café del mes' }));
    const enTodas = screen.getByRole('checkbox', { name: /también en todas sus otras compras/ });
    expect(enTodas).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Envío gratis en las entregas de la suscripción' }));
    expect(enTodas).toBeEnabled();
  });

  it('muestra junto a cada campo los errores del servidor', async () => {
    clienteAxios.put.mockRejectedValue({ response: { status: 400, data: { errores: {
      nombre: 'El nombre es obligatorio.',
      productos: 'Elige al menos una categoría o un producto que el cliente pueda recibir.'
    } } } });
    render(<GestorSuscripciones />);

    fireEvent.click(await screen.findByRole('button', { name: 'Editar Café del mes' }));
    fireEvent.change(screen.getByLabelText('Nombre del plan'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Revisa los datos marcados.');
    expect(screen.getByLabelText('Nombre del plan')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByText('El nombre es obligatorio.')).toBeInTheDocument();
    expect(screen.getByText(/Elige al menos una categoría/)).toBeInTheDocument();
    expect(clienteAxios.put).toHaveBeenCalledWith('ventas/admin/suscripciones/planes/1/', expect.any(Object));
  });

  it('un producto elegido que ya no está en el catálogo se puede quitar', async () => {
    responder({ planes: [plan({ productos: ['borrado'] })] });
    render(<GestorSuscripciones />);

    fireEvent.click(await screen.findByRole('button', { name: 'Editar Café del mes' }));
    const borrado = screen.getByRole('checkbox', { name: /ya no está en el catálogo/ });
    expect(borrado).toBeChecked();
    fireEvent.click(borrado);
    expect(screen.getByText(/Productos sueltos \(0 elegidos\)/)).toBeInTheDocument();
  });

  it('ordena los planes y guarda el orden', async () => {
    responder({ planes: [plan(), plan({ id: 2, nombre: 'Café semanal' })] });
    clienteAxios.put.mockResolvedValue({ data: { ids: [2, 1] } });
    render(<GestorSuscripciones />);

    expect(await screen.findByRole('button', { name: 'Subir Café del mes' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Subir Café semanal' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Café semanal: posición 1 de 2.');
    expect(clienteAxios.put).toHaveBeenCalledWith('ventas/admin/suscripciones/planes/orden/', { ids: [2, 1] });
    const lista = screen.getByRole('list', { name: /planes/i });
    expect(within(lista).getAllByRole('heading').map(h => h.textContent)).toEqual(['Café semanal', 'Café del mes']);
  });

  it('un plan con suscripciones no ofrece borrarlo; uno sin ellas se borra tras confirmar', async () => {
    responder({ planes: [plan({ suscripciones: 3 }), plan({ id: 2, nombre: 'Café semanal' })] });
    clienteAxios.delete.mockResolvedValue({});
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<GestorSuscripciones />);

    expect(await screen.findByText('3 suscripciones')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Borrar Café del mes' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Borrar Café semanal' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Borraste el plan "Café semanal".');
    expect(clienteAxios.delete).toHaveBeenCalledWith('ventas/admin/suscripciones/planes/2/');
    confirmar.mockRestore();
  });
});

const suscripcion = (cambios = {}) => ({
  id: 4, estado: 'ACTIVA', estado_texto: 'Activa', plan: plan(), producto: 'Etiopía Yirgacheffe · 250 g',
  entrega: { texto: 'Chilexpress: Los Aromos 1550, Ñuñoa' }, metodo_pago: 'TRANSFERENCIA',
  proxima_entrega: '2026-11-20', fecha_creacion: '2026-11-11T15:00:00Z', pedido_pendiente: null,
  cliente: { nombre: 'Ana Pérez', email: 'ana@ejemplo.cl' }, motivo_cancelacion: '', ...cambios
});

describe('GestorSuscriptores (vista Suscriptores)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clienteAxios.get.mockImplementation((url) => url === 'ventas/admin/suscripciones/planes/'
      ? Promise.resolve({ data: { planes: [plan()] } })
      : Promise.resolve({ data: { count: 1, results: [suscripcion({ pedido_pendiente: { orden_id: 55, total: 18990, ciclo_fecha: '2026-11-20' } })] } }));
  });

  afterEach(() => cleanup());

  it('muestra cada suscriptor con su próxima entrega y el pedido por pagar', async () => {
    render(<GestorSuscriptores />);

    const tarjeta = (await screen.findByRole('heading', { name: 'Ana Pérez · Café del mes' })).closest('article');
    expect(within(tarjeta).getByText('Activa')).toBeInTheDocument();
    expect(within(tarjeta).getByText('1 × Etiopía Yirgacheffe · 250 g')).toBeInTheDocument();
    expect(within(tarjeta).getByText('Transferencia bancaria')).toBeInTheDocument();
    expect(within(tarjeta).getByText('20 de noviembre de 2026')).toBeInTheDocument();
    expect(within(tarjeta).getByText(/Pedido #55 de \$18\.990/)).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('1 suscripción');
  });

  it('filtra por estado, plan, pago pendiente y búsqueda', async () => {
    render(<GestorSuscriptores />);
    await screen.findByRole('heading', { name: 'Ana Pérez · Café del mes' });

    fireEvent.change(screen.getByLabelText('Estado'), { target: { value: 'PAUSADA' } });
    await waitFor(() => expect(clienteAxios.get).toHaveBeenLastCalledWith('ventas/admin/suscripciones/',
      { params: { pagina: 1, estado: 'PAUSADA' } }));

    fireEvent.change(await screen.findByRole('combobox', { name: 'Plan' }), { target: { value: '1' } });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Solo con un pedido por pagar' }));
    fireEvent.change(screen.getByLabelText('Buscar'), { target: { value: ' ana ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Buscar' }));

    await waitFor(() => expect(clienteAxios.get).toHaveBeenLastCalledWith('ventas/admin/suscripciones/',
      { params: { pagina: 1, estado: 'PAUSADA', plan: '1', pago_pendiente: 1, buscar: 'ana' } }));
    expect(await screen.findByRole('status')).toHaveTextContent('1 suscripción con estos filtros');
  });

  it('la cancelada muestra su motivo y no su próxima entrega', async () => {
    clienteAxios.get.mockImplementation((url) => url === 'ventas/admin/suscripciones/planes/'
      ? Promise.resolve({ data: { planes: [] } })
      : Promise.resolve({ data: { count: 1, results: [suscripcion({ estado: 'CANCELADA', estado_texto: 'Cancelada',
        motivo_cancelacion: 'El cliente canceló su suscripción', proxima_entrega: null })] } }));
    render(<GestorSuscriptores />);

    expect(await screen.findByText('El cliente canceló su suscripción')).toBeInTheDocument();
    expect(screen.queryByText('Próxima entrega')).not.toBeInTheDocument();
  });
});

describe('AdminSidebar con suscripciones', () => {
  afterEach(() => cleanup());

  const barra = () => render(<AdminSidebar vistaActiva="dashboard" setVistaActiva={vi.fn()}
    setMostrandoFormulario={vi.fn()} setProductoAEditar={vi.fn()} navigate={vi.fn()} />);

  it('muestra Suscriptores solo con el módulo activo', () => {
    useConfiguracionTienda.mockReturnValue({ suscripciones_activas: false });
    barra();
    expect(screen.queryByRole('button', { name: 'Suscriptores' })).not.toBeInTheDocument();
    cleanup();

    useConfiguracionTienda.mockReturnValue({ suscripciones_activas: true });
    barra();
    expect(screen.getByRole('button', { name: 'Suscriptores' })).toBeInTheDocument();
  });
});
