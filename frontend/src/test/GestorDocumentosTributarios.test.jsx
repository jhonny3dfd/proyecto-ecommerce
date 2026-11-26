import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), patch: vi.fn() } }));

import clienteAxios from '../components/auth/axiosConfig';
import GestorDocumentosTributarios from '../components/GestorDocumentosTributarios';

const grupo = () => screen.getByRole('group', { name: 'Tu modelo de emisión en el SII' });
const opcion = (nombre) => within(grupo()).getByRole('radio', { name: nombre });
const VOUCHER = /El comprobante del pago con tarjeta vale como boleta/;
const SIEMPRE = /Siempre emito boleta/;

describe('GestorDocumentosTributarios (boletas y facturas)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clienteAxios.get.mockResolvedValue({ data: { modelo_emision: 'VOUCHER' } });
  });

  afterEach(() => cleanup());

  it('muestra el modelo guardado, con cada opción explicada y la guía de qué emitir', async () => {
    render(<GestorDocumentosTributarios />);

    expect(await screen.findByRole('radio', { name: VOUCHER })).toBeChecked();
    expect(opcion(SIEMPRE)).not.toBeChecked();
    expect(opcion(SIEMPRE)).toHaveAccessibleDescription(/Elige el mismo que declaraste en sii\.cl.*Todas las ventas piden boleta/);
    expect(screen.getByText('Transferencia:').closest('li')).toHaveTextContent('siempre emites boleta');
    expect(screen.getByText('Compra como empresa:').closest('li')).toHaveTextContent('siempre emites factura');
    expect(screen.getByText(/135 UF/).closest('li')).toHaveTextContent('nombre y el RUT de quien paga');
    expect(screen.getByRole('link', { name: /Boleta electrónica gratuita del SII/ }))
      .toHaveAttribute('href', 'https://www.sii.cl/servicios_online/3532-.html');
  });

  it('guarda el modelo que eligió la tienda', async () => {
    clienteAxios.patch.mockResolvedValue({ data: { modelo_emision: 'SIEMPRE_BOLETA' } });
    render(<GestorDocumentosTributarios />);

    fireEvent.click(await screen.findByRole('radio', { name: SIEMPRE }));
    fireEvent.click(screen.getByRole('button', { name: 'Guardar modelo de emisión' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Modelo de emisión guardado');
    expect(clienteAxios.patch).toHaveBeenCalledWith('configuracion/negocio/', { modelo_emision: 'SIEMPRE_BOLETA' });
    expect(opcion(SIEMPRE)).toBeChecked();
  });

  it('avisa si no pudo guardar', async () => {
    clienteAxios.patch.mockRejectedValue({ response: { status: 500 } });
    render(<GestorDocumentosTributarios />);

    fireEvent.click(await screen.findByRole('button', { name: 'Guardar modelo de emisión' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo guardar el modelo de emisión');
  });

  it('avisa si no pudo cargar la configuración', async () => {
    clienteAxios.get.mockRejectedValue(new Error('Network Error'));
    render(<GestorDocumentosTributarios />);

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo cargar el modelo de emisión');
  });
});
