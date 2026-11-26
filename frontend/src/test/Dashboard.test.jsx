import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Dashboard from '../components/Dashboard';
import clienteAxios from '../components/auth/axiosConfig';
import { completarSerie, textoRango } from '../components/dashboard/formato';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn() } }));

// recharts mide su contenedor: jsdom no trae ResizeObserver
globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

const METRICAS = {
  periodo: { clave: 'ESTE_MES', desde: '2026-11-01', hasta: '2026-11-05', agrupacion: 'DIA' },
  anterior: { desde: '2026-10-01', hasta: '2026-10-05' },
  tarjetas: {
    ventas: 1240000, variacion_ventas: 12, pedidos: 38, diferencia_pedidos: 5, ticket_promedio: 32632,
    variacion_ticket: -4, clientes_nuevos: 12,
  },
  serie: [{ fecha: '2026-11-02', total: 50000, pedidos: 2 }],
  mas_vendidos: [{ producto_id: 'p1', nombre: 'Polerón negro', unidades: 14, total: 350000 }],
  ultimas_ordenes: [{ id: 1042, fecha_creacion: '2026-11-05T10:00:00-03:00', estado: 'ENVIADO', total_final: 24990,
    cliente: 'Ana Pérez' }],
  detalles: {
    medios_pago: [{ nombre: 'Transbank Webpay Plus', total: 62000, pedidos: 3, porcentaje: 62 }],
    entregas: [], comunas: [],
    cancelaciones: [{ causa: 'PAGO_RECHAZADO', nombre: 'Pago rechazado o anulado', cantidad: 3 }],
    cupones: [{ codigo: 'BIENVENIDA', usos: 7, descontado: 14000 }],
    clientes: { nuevos: 12, recurrentes: 4, registrados: 10, invitados: 6 },
    calificacion: { promedio: 4.3, cantidad: 12 },
  },
};

const PENDIENTES = {
  al_dia: false,
  tareas: [
    { tarea: 'POR_PREPARAR', cantidad: 3, por_vencer: 0 },
    { tarea: 'TRANSFERENCIAS', cantidad: 1, por_vencer: 1 },
    { tarea: 'DOCUMENTOS', cantidad: 2, por_vencer: 0 },
    { tarea: 'RESENAS', cantidad: 1, por_vencer: 0 },
  ],
  agotadas: [{ producto_id: 'p1', producto: 'Polerón', sku: 'POL-S', detalle: 'Talla: S', stock: 0 }],
  stock_bajo: [],
};

function responder({ metricas = METRICAS, pendientes = PENDIENTES } = {}) {
  clienteAxios.get.mockImplementation((url) => {
    if (url === 'ventas/dashboard/pendientes/') return Promise.resolve({ data: pendientes });
    return typeof metricas === 'function' ? metricas() : Promise.resolve({ data: metricas });
  });
}

async function renderDashboard(onIrA = vi.fn()) {
  render(<Dashboard onIrA={onIrA} />);
  await screen.findByRole('heading', { name: 'Para hoy' });
  // Las cifras y los pendientes llegan por separado
  await waitFor(() => expect(clienteAxios.get).toHaveBeenCalledTimes(2));
  await screen.findAllByText(/Todo al día|por preparar|por aprobar/, { selector: 'li > span, p' });
  return onIrA;
}

// El texto visible de una tarea (dentro de su "Ver" se repite, oculto, para el lector de pantalla)
const tarea = (texto) => screen.getByText(texto, { selector: 'li > span' });

describe('Dashboard (RF-03.1)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    responder();
  });

  afterEach(cleanup);

  it('muestra las 4 cifras con la comparación escrita, sin colores', async () => {
    await renderDashboard();

    expect(await screen.findByText('+12 % frente al periodo anterior')).toBeInTheDocument();
    expect(screen.getByText('5 pedidos más que el periodo anterior')).toBeInTheDocument();
    expect(screen.getByText('−4 % frente al periodo anterior')).toBeInTheDocument();
    expect(screen.getByText(/1 al 5 de noviembre de 2026 · comparado con 1 al 5 de octubre de 2026/))
      .toBeInTheDocument();
    const titulos = [...document.querySelectorAll('.admin-indicador-etiqueta')].map((titulo) => titulo.textContent);
    expect(titulos).toEqual(['Ventas', 'Pedidos', 'Ticket promedio', 'Clientes nuevos']);
  });

  it('desde el inicio no hay con qué comparar', async () => {
    responder({ metricas: { ...METRICAS, anterior: null,
      periodo: { clave: 'DESDE_INICIO', desde: null, hasta: '2026-11-05', agrupacion: 'MES' } } });

    await renderDashboard();

    expect(await screen.findAllByText('Desde la primera venta')).not.toHaveLength(0);
    expect(screen.queryByText(/frente al periodo anterior/)).not.toBeInTheDocument();
  });

  it('cambiar el periodo vuelve a pedir las cifras', async () => {
    await renderDashboard();

    fireEvent.change(screen.getByLabelText('Periodo'), { target: { value: 'ULTIMOS_30' } });

    await waitFor(() => expect(clienteAxios.get).toHaveBeenCalledWith('ventas/dashboard/metricas/',
      { params: { periodo: 'ULTIMOS_30' } }));
  });

  it('el rango personalizado se pide al aplicarlo', async () => {
    await renderDashboard();

    fireEvent.change(screen.getByLabelText('Periodo'), { target: { value: 'PERSONALIZADO' } });
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-10-03' } });
    fireEvent.change(screen.getByLabelText('Hasta'), { target: { value: '2026-10-09' } });
    expect(clienteAxios.get).not.toHaveBeenCalledWith('ventas/dashboard/metricas/',
      expect.objectContaining({ params: expect.objectContaining({ periodo: 'PERSONALIZADO' }) }));
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar' }));

    await waitFor(() => expect(clienteAxios.get).toHaveBeenCalledWith('ventas/dashboard/metricas/',
      { params: { periodo: 'PERSONALIZADO', desde: '2026-10-03', hasta: '2026-10-09' } }));
  });

  it('"Para hoy" lista lo pendiente y lo urgente', async () => {
    await renderDashboard();
    const paraHoy = screen.getByRole('region', { name: 'Para hoy' });

    expect(tarea('3 pedidos pagados por preparar')).toBeInTheDocument();
    expect(tarea(/1 transferencia por validar/)).toHaveTextContent('1 transferencia por validar (1 vence en menos de 24 horas)');
    expect(tarea('2 boletas, facturas o notas de crédito por emitir')).toBeInTheDocument();
    expect(within(paraHoy).getByText('1 variante agotada')).toBeInTheDocument();
    expect(within(paraHoy).queryByText(/Todo al día/)).not.toBeInTheDocument();
  });

  it('sin pendientes dice "Todo al día"', async () => {
    responder({ pendientes: { al_dia: true, tareas: [], agotadas: [], stock_bajo: [] } });

    await renderDashboard();

    const paraHoy = screen.getByRole('region', { name: 'Para hoy' });
    expect(within(paraHoy).getByText(/Todo al día/)).toBeInTheDocument();
    expect(within(paraHoy).queryByRole('button')).not.toBeInTheDocument();
  });

  it('"Ver" abre la vista con su filtro', async () => {
    const onIrA = await renderDashboard();

    fireEvent.click(screen.getByRole('button', { name: /Ver 3 pedidos pagados por preparar/ }));
    fireEvent.click(screen.getByRole('button', { name: /Ver 2 boletas/ }));
    fireEvent.click(screen.getByRole('button', { name: /Ver 1 reseña por aprobar/ }));
    fireEvent.click(screen.getByRole('button', { name: /Ir al inventario/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Ver todos los pedidos/ }));

    expect(onIrA.mock.calls).toEqual([
      ['ventas', { estado: 'PAGADO' }], ['ventas', { documento: true }], ['resenas', undefined],
      ['inventario'], ['ventas'],
    ]);
  });

  it('las pestañas de "Más detalles" se recorren con el teclado', async () => {
    await renderDashboard();
    const cancelaciones = await screen.findByRole('tab', { name: 'Cancelaciones' });

    expect(screen.getByRole('tab', { name: 'Cómo compran' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('Transbank Webpay Plus')).toBeInTheDocument();

    fireEvent.keyDown(screen.getByRole('tab', { name: 'Cómo compran' }), { key: 'ArrowRight' });
    expect(cancelaciones).toHaveAttribute('aria-selected', 'true');
    expect(cancelaciones).toHaveFocus();
    expect(screen.getByText('Pago rechazado o anulado')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Clientes' }));
    expect(screen.getByText('4,3 de 5')).toBeInTheDocument();
  });

  it('si fallan los pendientes, las cifras igual se muestran', async () => {
    clienteAxios.get.mockImplementation((url) => (url === 'ventas/dashboard/pendientes/'
      ? Promise.reject(new Error('caído')) : Promise.resolve({ data: METRICAS })));

    render(<Dashboard />);

    expect(await screen.findByText('No fue posible cargar los pendientes.')).toBeInTheDocument();
    expect(await screen.findByText('Polerón negro')).toBeInTheDocument();
  });

  describe('exportar las ventas a Excel', () => {
    const EXCEL = new Blob(['xlsx']);
    let descargas;

    // El Excel responde aparte; lo demás, como siempre
    function responderExcel(excel) {
      clienteAxios.get.mockImplementation((url) => {
        if (url === 'ventas/dashboard/exportar/') return excel();
        if (url === 'ventas/dashboard/pendientes/') return Promise.resolve({ data: PENDIENTES });
        return Promise.resolve({ data: METRICAS });
      });
    }

    beforeEach(() => {
      descargas = [];
      // jsdom no trae URL.createObjectURL ni descarga archivos: se anota el nombre con que se habría guardado
      URL.createObjectURL = vi.fn(() => 'blob:excel');
      URL.revokeObjectURL = vi.fn();
      vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function anotar() {
        descargas.push({ nombre: this.download, direccion: this.getAttribute('href') });
      });
    });

    afterEach(() => vi.restoreAllMocks());

    it('descarga el archivo del periodo que muestra el dashboard', async () => {
      responderExcel(() => Promise.resolve({
        data: EXCEL, headers: { 'content-disposition': 'attachment; filename="ventas_2026-11-01_a_2026-11-05.xlsx"' },
      }));
      await renderDashboard();
      fireEvent.change(screen.getByLabelText('Periodo'), { target: { value: 'MES_ANTERIOR' } });

      fireEvent.click(screen.getByRole('button', { name: 'Exportar ventas a Excel' }));

      await waitFor(() => expect(descargas).toEqual(
        [{ nombre: 'ventas_2026-11-01_a_2026-11-05.xlsx', direccion: 'blob:excel' }]));
      expect(clienteAxios.get).toHaveBeenCalledWith('ventas/dashboard/exportar/',
        { params: { periodo: 'MES_ANTERIOR' }, responseType: 'blob' });
      expect(URL.createObjectURL).toHaveBeenCalledWith(EXCEL);
      expect(screen.getByRole('button', { name: 'Exportar ventas a Excel' })).toBeEnabled();
    });

    it('con un rango personalizado exporta el que se aplicó', async () => {
      responderExcel(() => Promise.resolve({ data: EXCEL, headers: {} }));
      await renderDashboard();
      fireEvent.change(screen.getByLabelText('Periodo'), { target: { value: 'PERSONALIZADO' } });
      fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-10-03' } });
      fireEvent.change(screen.getByLabelText('Hasta'), { target: { value: '2026-10-09' } });
      fireEvent.click(screen.getByRole('button', { name: 'Aplicar' }));

      fireEvent.click(screen.getByRole('button', { name: 'Exportar ventas a Excel' }));

      await waitFor(() => expect(clienteAxios.get).toHaveBeenCalledWith('ventas/dashboard/exportar/',
        { params: { periodo: 'PERSONALIZADO', desde: '2026-10-03', hasta: '2026-10-09' }, responseType: 'blob' }));
      // Sin el nombre del backend igual se descarga, con uno genérico
      await waitFor(() => expect(descargas).toEqual([{ nombre: 'ventas.xlsx', direccion: 'blob:excel' }]));
    });

    it('mientras se prepara no deja pedirlo dos veces, y si falla lo avisa', async () => {
      let fallar;
      responderExcel(() => new Promise((_, rechazar) => { fallar = rechazar; }));
      await renderDashboard();

      fireEvent.click(screen.getByRole('button', { name: 'Exportar ventas a Excel' }));

      expect(await screen.findByRole('button', { name: 'Preparando el Excel…' })).toBeDisabled();
      fallar(new Error('caído'));
      expect(await screen.findByRole('alert')).toHaveTextContent('No fue posible exportar las ventas.');
      expect(descargas).toEqual([]);
      expect(screen.getByRole('button', { name: 'Exportar ventas a Excel' })).toBeEnabled();
    });
  });
});

describe('formato del dashboard', () => {
  it('completa con 0 los días sin ventas', () => {
    const serie = completarSerie([{ fecha: '2026-11-02', total: 5, pedidos: 1 }],
      { desde: '2026-11-01', hasta: '2026-11-03', agrupacion: 'DIA' });

    expect(serie.map((p) => [p.fecha, p.total])).toEqual([['2026-11-01', 0], ['2026-11-02', 5], ['2026-11-03', 0]]);
  });

  it('completa los meses y cruza el año', () => {
    const serie = completarSerie([], { desde: '2025-11-01', hasta: '2026-01-20', agrupacion: 'MES' });

    expect(serie.map((p) => p.fecha)).toEqual(['2025-11-01', '2025-12-01', '2026-01-01']);
  });

  it('escribe los rangos', () => {
    expect(textoRango('2026-11-01', '2026-11-05')).toBe('1 al 5 de noviembre de 2026');
    expect(textoRango('2026-10-25', '2026-11-02')).toBe('25 de octubre al 2 de noviembre de 2026');
    expect(textoRango('2025-12-30', '2026-01-02')).toBe('30 de diciembre de 2025 al 2 de enero de 2026');
  });
});
