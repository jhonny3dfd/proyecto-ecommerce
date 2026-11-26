import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest';
import GestorPedidos from '../components/GestorPedidos';
import clienteAxios from '../components/auth/axiosConfig';


vi.mock('../components/auth/axiosConfig', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  }
}));

const pagina = (count, results = [{ id: 1, estado: 'PENDIENTE', requiere_revision: false, transiciones_permitidas: [] }]) =>
  ({ data: { count, results } });

const pedidoBase = (cambios = {}) => ({
  id: 1,
  estado: 'PAGADO',
  total_final: 15000,
  email_cliente: 'cliente@ejemplo.cl',
  requiere_revision: false,
  transiciones_permitidas: [],
  ...cambios,
});

describe('GestorPedidos - Interfaz de Ventas', () => {
  afterEach(cleanup);

  beforeEach(() => {
    clienteAxios.get.mockReset();
  });

  it('renderiza correctamente los filtros de estado, revisión y controles de paginación', async () => {
    // Preparamos el mock para devolver 25 pedidos
    clienteAxios.get.mockResolvedValueOnce(pagina(25));

    render(<GestorPedidos />);

    // Esperamos a que termine de cargar y muestre el texto de resultados
    await waitFor(() => {
      expect(screen.getByText(/25 pedido\(s\) encontrado\(s\)/i)).toBeInTheDocument();
    });

    // El filtro por estado tiene su etiqueta
    expect(screen.getByRole('combobox', { name: 'Estado' })).toBeInTheDocument();
    expect(screen.getByLabelText(/Requiere revisión/i)).toBeInTheDocument();

    const btnAnterior = screen.getByRole('button', { name: /Anterior/i });
    const btnSiguiente = screen.getByRole('button', { name: /Siguiente/i });

    // Al estar en la página 1, el botón Anterior debe estar deshabilitado
    expect(btnAnterior).toBeDisabled();
    // Al haber 25 pedidos (2 páginas), el botón Siguiente debe estar habilitado
    expect(btnSiguiente).not.toBeDisabled();
  });

  it('al filtrar por estado pide ese estado y los filtros siguen a la vista', async () => {
    clienteAxios.get.mockResolvedValueOnce(pagina(25)).mockResolvedValueOnce(pagina(0, []));
    render(<GestorPedidos />);
    const estado = await screen.findByRole('combobox', { name: 'Estado' });

    fireEvent.change(estado, { target: { value: 'ENVIADO' } });

    // El filtro no se desmonta mientras carga: el foco no se pierde
    expect(screen.getByRole('combobox', { name: 'Estado' })).toBe(estado);
    expect(await screen.findByText('No hay pedidos despachados en este momento.')).toBeInTheDocument();
    expect(clienteAxios.get).toHaveBeenLastCalledWith('ventas/admin/ordenes/', { params: { pagina: 1, estado: 'ENVIADO' } });
  });

  it('abre con el filtro que pide el dashboard: órdenes de transporte con error', async () => {
    clienteAxios.get.mockResolvedValueOnce(pagina(0, []));

    render(<GestorPedidos filtroInicial={{ ordenTransporte: true }} />);

    expect(await screen.findByText('No hay órdenes de transporte con error.')).toBeInTheDocument();
    expect(screen.getByLabelText('Con error en la orden de transporte')).toBeChecked();
    expect(clienteAxios.get).toHaveBeenCalledWith('ventas/admin/ordenes/', { params: { pagina: 1, orden_transporte: 'error' } });
  });

  it('abre con el estado que pide el dashboard: pagados por preparar', async () => {
    clienteAxios.get.mockResolvedValueOnce(pagina(1));

    render(<GestorPedidos filtroInicial={{ estado: 'PAGADO' }} />);

    expect(await screen.findByRole('combobox', { name: 'Estado' })).toHaveValue('PAGADO');
    expect(clienteAxios.get).toHaveBeenCalledWith('ventas/admin/ordenes/', { params: { pagina: 1, estado: 'PAGADO' } });
  });

  it('una entrega coordinada sin dirección avisa que se acuerda con el comprador', async () => {
    clienteAxios.get.mockResolvedValueOnce(pagina(2, [
      { id: 1, estado: 'PAGADO', transiciones_permitidas: [], proveedor_logistico: 'ENTREGA_COORDINADA',
        direccion_envio_snapshot: {} },
      { id: 2, estado: 'PAGADO', transiciones_permitidas: [], proveedor_logistico: 'ENTREGA_COORDINADA',
        direccion_envio_snapshot: { calle: 'Los Aromos', numero: '1550', comuna: 'Ñuñoa' } },
    ]));
    render(<GestorPedidos />);

    expect(await screen.findByText('Dirección por acordar con el comprador')).toBeInTheDocument();
    expect(screen.getByText('Los Aromos 1550, Ñuñoa')).toBeInTheDocument();
  });

  it('marca la entrega de una suscripción con su fecha', async () => {
    clienteAxios.get.mockResolvedValueOnce(pagina(2, [
      pedidoBase({ id: 1, suscripcion: 7, ciclo_fecha: '2026-11-14' }),
      pedidoBase({ id: 2, suscripcion: null, ciclo_fecha: null }),
    ]));
    render(<GestorPedidos />);

    expect(await screen.findByText('Suscripción · 14-11-2026')).toBeInTheDocument();
    expect(screen.getAllByText(/^Suscripción/)).toHaveLength(1);
  });

  it('el filtro de boleta o factura pendiente pide solo esos pedidos', async () => {
    clienteAxios.get.mockResolvedValueOnce(pagina(25)).mockResolvedValueOnce(pagina(0, []));
    render(<GestorPedidos />);

    fireEvent.click(await screen.findByRole('checkbox', { name: 'Solo con boleta o factura pendiente' }));

    expect(await screen.findByText('No hay boletas, facturas ni notas de crédito pendientes.')).toBeInTheDocument();
    expect(clienteAxios.get).toHaveBeenLastCalledWith('ventas/admin/ordenes/',
      { params: { pagina: 1, documento: 'pendiente' } });
  });

  it('si la página pedida ya no existe, vuelve a la anterior sin mostrar un error', async () => {
    clienteAxios.get
      .mockResolvedValueOnce(pagina(25))
      .mockRejectedValueOnce({ response: { status: 404 } })
      .mockResolvedValueOnce(pagina(20));
    render(<GestorPedidos />);

    fireEvent.click(await screen.findByRole('button', { name: /Siguiente/i }));

    expect(await screen.findByText(/20 pedido\(s\) encontrado\(s\)/i)).toBeInTheDocument();
    expect(clienteAxios.get).toHaveBeenLastCalledWith('ventas/admin/ordenes/', { params: { pagina: 1 } });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('muestra un error cuando falla la carga de pedidos', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    clienteAxios.get.mockRejectedValueOnce(new Error('Error de conexión'));

    render(<GestorPedidos />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudieron cargar los pedidos.',
    );

    expect(screen.getByText('No hay pedidos registrados en la tienda.')).toBeInTheDocument();
  });

  it('envía el filtro de pedidos que requieren revisión', async () => {
    clienteAxios.get
      .mockResolvedValueOnce(pagina(1))
      .mockResolvedValueOnce(pagina(0, []));

    render(<GestorPedidos />);

    fireEvent.click(await screen.findByLabelText('Requiere revisión'));

    expect(
      await screen.findByText('No hay pedidos que requieran revisión.'),
    ).toBeInTheDocument();

    expect(clienteAxios.get).toHaveBeenLastCalledWith(
      'ventas/admin/ordenes/',
      { params: { pagina: 1, requiere_revision: 'true' } },
    );
  });

  it('permite cambiar el estado de un pedido y muestra confirmación', async () => {
    const pedido = pedidoBase({
      transiciones_permitidas: ['EN_PREPARACION'],
    });

    clienteAxios.get.mockResolvedValue(pagina(1, [pedido]));
    clienteAxios.patch.mockResolvedValue({
      data: { estado: 'EN_PREPARACION', requiere_revision: false },
    });

    render(<GestorPedidos />);

    const selector = await screen.findByRole('combobox', {
      name: 'Estado del pedido #1',
    });

    fireEvent.change(selector, { target: { value: 'EN_PREPARACION' } });

    expect(clienteAxios.patch).toHaveBeenCalledWith(
      'ventas/admin/ordenes/1/estado/',
      { estado: 'EN_PREPARACION' },
    );

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Pedido #1 actualizado a En Preparación.',
    );
  });

  it('no cancela un pedido si el administrador rechaza la confirmación', async () => {
    const pedido = pedidoBase({
      transiciones_permitidas: ['CANCELADO'],
    });

    clienteAxios.get.mockResolvedValue(pagina(1, [pedido]));
    vi.spyOn(window, 'confirm').mockReturnValue(false);

    render(<GestorPedidos />);

    const selector = await screen.findByRole('combobox', {
      name: 'Estado del pedido #1',
    });

    fireEvent.change(selector, { target: { value: 'CANCELADO' } });

    expect(window.confirm).toHaveBeenCalledWith(
      expect.stringContaining('¿Cancelar el pedido #1?'),
    );

    expect(clienteAxios.patch).not.toHaveBeenCalled();
  });

  it('muestra el motivo de revisión cuando el backend marca el pedido para revisión', async () => {
    const pedido = pedidoBase({
      transiciones_permitidas: ['EN_PREPARACION'],
    });

    clienteAxios.get.mockResolvedValue(pagina(1, [pedido]));
    clienteAxios.patch.mockResolvedValue({
      data: {
        estado: 'EN_PREPARACION',
        requiere_revision: true,
        motivo_revision: 'Stock pendiente de verificar',
      },
    });

    render(<GestorPedidos />);

    fireEvent.change(
      await screen.findByRole('combobox', { name: 'Estado del pedido #1' }),
      { target: { value: 'EN_PREPARACION' } },
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Pedido #1 quedó En Preparación, pero requiere revisión: Stock pendiente de verificar.',
    );
  });

  it('muestra el error devuelto por el backend al cambiar el estado', async () => {
    const pedido = pedidoBase({
      transiciones_permitidas: ['EN_PREPARACION'],
    });

    clienteAxios.get.mockResolvedValue(pagina(1, [pedido]));
    clienteAxios.patch.mockRejectedValue({
      response: { data: { detail: 'No se puede modificar este pedido.' } },
    });

    render(<GestorPedidos />);

    fireEvent.change(
      await screen.findByRole('combobox', { name: 'Estado del pedido #1' }),
      { target: { value: 'EN_PREPARACION' } },
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo actualizar el pedido #1: No se puede modificar este pedido.',
    );
  });

  it('permite marcar una revisión como resuelta', async () => {
    const pedido = pedidoBase({
      requiere_revision: true,
      motivo_revision: 'Reembolso pendiente',
    });

    clienteAxios.get.mockResolvedValue(pagina(1, [pedido]));
    clienteAxios.post.mockResolvedValue({ data: {} });
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<GestorPedidos />);

    fireEvent.click(await screen.findByRole('button', { name: 'Marcar como revisada' }));

    expect(clienteAxios.post).toHaveBeenCalledWith(
      'ventas/admin/ordenes/1/revision/resolver/',
    );

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Revisión del pedido #1 marcada como resuelta.',
    );
  });

  it('no resuelve una revisión si el administrador rechaza la confirmación', async () => {
    const pedido = pedidoBase({ requiere_revision: true });

    clienteAxios.get.mockResolvedValue(pagina(1, [pedido]));
    vi.spyOn(window, 'confirm').mockReturnValue(false);

    render(<GestorPedidos />);

    fireEvent.click(await screen.findByRole('button', { name: 'Marcar como revisada' }));

    expect(clienteAxios.post).not.toHaveBeenCalled();
  });

  it('permite registrar un pago recibido fuera de plazo', async () => {
    const pedido = pedidoBase({
      estado: 'CANCELADO',
      motivo_cancelacion: 'Pago no recibido a tiempo',
    });

    clienteAxios.get.mockResolvedValue(pagina(1, [pedido]));
    clienteAxios.post.mockResolvedValue({ data: {} });

    render(<GestorPedidos />);

    fireEvent.click(
      await screen.findByRole('button', {
        name: 'Registrar pago recibido fuera de plazo',
      }),
    );

    expect(clienteAxios.post).toHaveBeenCalledWith(
      'ventas/admin/ordenes/1/pago-fuera-plazo/',
    );

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Pago fuera de plazo registrado. El pedido #1 quedó pendiente de revisión.',
    );
  });

  it('muestra un error si falla el registro de un pago fuera de plazo', async () => {
    const pedido = pedidoBase({
      estado: 'CANCELADO',
      motivo_cancelacion: 'Pago no recibido a tiempo',
    });

    clienteAxios.get.mockResolvedValue(pagina(1, [pedido]));
    clienteAxios.post.mockRejectedValue({
      response: { data: { detail: 'El pago ya fue registrado.' } },
    });

    render(<GestorPedidos />);

    fireEvent.click(
      await screen.findByRole('button', {
        name: 'Registrar pago recibido fuera de plazo',
      }),
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo registrar el pago fuera de plazo del pedido #1: El pago ya fue registrado.',
    );
  });

  it('permite generar una orden de transporte y muestra su número de seguimiento', async () => {
    const pedido = pedidoBase({
      proveedor_logistico: 'STARKEN',
      puede_generar_orden_transporte: true,
    });

    clienteAxios.get.mockResolvedValue(pagina(1, [pedido]));
    clienteAxios.post.mockResolvedValue({
      data: { numero_seguimiento_tracking: 'STK123456' },
    });

    render(<GestorPedidos />);

    fireEvent.click(await screen.findByRole('button', { name: 'Generar OT' }));

    expect(clienteAxios.post).toHaveBeenCalledWith(
      'ventas/admin/ordenes/1/orden-transporte/',
    );

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Orden de transporte STK123456 generada para el pedido #1.',
    );
  });

  it('permite reintentar una orden de transporte que falló', async () => {
    const pedido = pedidoBase({
      proveedor_logistico: 'STARKEN',
      puede_generar_orden_transporte: true,
      error_orden_transporte: 'Error de conexión con el courier',
    });

    clienteAxios.get.mockResolvedValue(pagina(1, [pedido]));
    clienteAxios.post.mockResolvedValue({
      data: { numero_seguimiento_tracking: 'STK789' },
    });

    render(<GestorPedidos />);

    expect(
      await screen.findByText('Error de conexión con el courier'),
    ).toBeInTheDocument();

    fireEvent.click(await screen.findByRole('button', { name: 'Reintentar OT' }));

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Orden de transporte STK789 generada para el pedido #1.',
    );
  });

  it('muestra el error cuando falla la generación de la orden de transporte', async () => {
    const pedido = pedidoBase({
      proveedor_logistico: 'STARKEN',
      puede_generar_orden_transporte: true,
    });

    clienteAxios.get.mockResolvedValue(pagina(1, [pedido]));
    clienteAxios.post.mockRejectedValue({
      response: { data: { detail: 'Courier no disponible.' } },
    });

    render(<GestorPedidos />);

    fireEvent.click(await screen.findByRole('button', { name: 'Generar OT' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo generar la orden de transporte del pedido #1: Courier no disponible.',
    );
  });

  it('muestra el aviso cuando se guarda el documento del pedido', async () => {
    clienteAxios.get.mockResolvedValue(
      pagina(1, [
        pedidoBase({
          documento_requerido: 'BOLETA',
          documento_por_emitir: 'BOLETA',
        }),
      ]),
    );

    clienteAxios.post.mockResolvedValue({ data: {} });

    render(<GestorPedidos />);

    const campoFolio = await screen.findByRole('textbox', {
      name: 'Folio de la boleta del pedido #1',
    });

    fireEvent.change(campoFolio, { target: { value: '12345' } });

    fireEvent.click(
      screen.getByRole('button', { name: 'Guardar' }),
    );

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Boleta N° 12345 anotada en el pedido #1.',
    );
  });

  it('muestra los datos de empresa y destinatario cuando están disponibles', async () => {
    const pedido = pedidoBase({
      nombre_destinatario: 'María Pérez',
      telefono_destinatario: '+56912345678',
      datos_empresa: {
        razon_social: 'Comercial Ejemplo SpA',
        rut: '76.123.456-7',
        giro: 'Comercio',
        direccion: 'Av. Central 123',
        correo: 'facturas@ejemplo.cl',
      },
    });

    clienteAxios.get.mockResolvedValueOnce(pagina(1, [pedido]));

    render(<GestorPedidos />);

    expect(await screen.findByText(/Recibe: María Pérez/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '+56912345678' })).toHaveAttribute(
      'href',
      'tel:+56912345678',
    );
    expect(screen.getByText(/Comercial Ejemplo SpA/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'facturas@ejemplo.cl' })).toHaveAttribute(
      'href',
      'mailto:facturas@ejemplo.cl',
    );
  });

  it('muestra el motivo de cancelación de un pedido cancelado', async () => {
    const pedido = pedidoBase({
      estado: 'CANCELADO',
      motivo_cancelacion: 'Cancelado por solicitud del comprador',
    });

    clienteAxios.get.mockResolvedValueOnce(pagina(1, [pedido]));

    render(<GestorPedidos />);

    expect(
      await screen.findByText('Cancelado por solicitud del comprador'),
    ).toBeInTheDocument();
  });
});
