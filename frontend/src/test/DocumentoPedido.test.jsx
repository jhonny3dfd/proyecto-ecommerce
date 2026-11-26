import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

vi.mock('../components/auth/axiosConfig', () => ({ default: { post: vi.fn() } }));

import clienteAxios from '../components/auth/axiosConfig';
import DocumentoPedido from '../components/DocumentoPedido';

const pedido = (extra) => ({
  id: 12, estado: 'PAGADO', documento_requerido: 'BOLETA', documento_por_emitir: 'BOLETA', folio_documento: '',
  folio_nota_credito: '', ...extra,
});

function mostrar(datos, onGuardado = vi.fn()) {
  render(<DocumentoPedido pedido={pedido(datos)} deshabilitado={false} onGuardado={onGuardado} />);
  return onGuardado;
}

const anotar = (nombre, folio) => {
  fireEvent.change(screen.getByRole('textbox', { name: nombre }), { target: { value: folio } });
  fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));
};

describe('DocumentoPedido: boleta, factura o nota de crédito del pedido', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it('una boleta pendiente se anota con su folio y avisa al panel', async () => {
    clienteAxios.post.mockResolvedValue({ data: {} });
    const onGuardado = mostrar({});

    expect(screen.getByText('Boleta pendiente')).toBeInTheDocument();
    anotar('Folio de la boleta del pedido #12', '123');

    await vi.waitFor(() => expect(onGuardado).toHaveBeenCalledWith('Boleta N° 123 anotada en el pedido #12.'));
    expect(clienteAxios.post).toHaveBeenCalledWith('ventas/admin/ordenes/12/documento/', { folio: '123' });
  });

  it('una factura pendiente pide el folio de la factura', () => {
    mostrar({ documento_requerido: 'FACTURA', documento_por_emitir: 'FACTURA' });
    expect(screen.getByText('Factura pendiente')).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Folio de la factura del pedido #12' })).toBeRequired();
  });

  it('el error de la tienda queda bajo el campo, asociado a él', async () => {
    clienteAxios.post.mockRejectedValue({ response: { status: 400, data: {
      folio: ['El folio son solo números, de 1 a 10 dígitos.'] } } });
    const onGuardado = mostrar({});
    anotar('Folio de la boleta del pedido #12', 'B-1');

    const campo = screen.getByRole('textbox', { name: 'Folio de la boleta del pedido #12' });
    expect(await screen.findByText('El folio son solo números, de 1 a 10 dígitos.')).toBeInTheDocument();
    expect(campo).toHaveAttribute('aria-invalid', 'true');
    expect(campo).toHaveAccessibleDescription('El folio son solo números, de 1 a 10 dígitos.');
    expect(onGuardado).not.toHaveBeenCalled();
  });

  it('un folio anotado se muestra y se puede corregir', async () => {
    clienteAxios.post.mockResolvedValue({ data: {} });
    const onGuardado = mostrar({ documento_por_emitir: null, folio_documento: '123' });

    expect(screen.getByText('Boleta N° 123')).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Corregir el folio de la boleta del pedido #12' }));
    expect(screen.getByRole('textbox', { name: 'Folio de la boleta del pedido #12' })).toHaveValue('123');
    anotar('Folio de la boleta del pedido #12', '132');

    await vi.waitFor(() => expect(onGuardado).toHaveBeenCalledWith('Boleta N° 132 anotada en el pedido #12.'));
  });

  it('se puede cancelar una corrección', () => {
    mostrar({ documento_por_emitir: null, folio_documento: '123' });
    fireEvent.click(screen.getByRole('button', { name: /Corregir/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('un cancelado con boleta pide la nota de crédito, sin corregir la boleta', () => {
    mostrar({ estado: 'CANCELADO', documento_por_emitir: 'NOTA_CREDITO', folio_documento: '120' });

    expect(screen.getByText('Nota de crédito pendiente')).toBeInTheDocument();
    expect(screen.getByText('Boleta N° 120')).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Folio de la nota de crédito del pedido #12' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Corregir/ })).not.toBeInTheDocument();
  });

  it('un cancelado con su nota de crédito anotada muestra los dos folios y corrige la nota', () => {
    mostrar({ estado: 'CANCELADO', documento_por_emitir: null, folio_documento: '120', folio_nota_credito: '7' });

    expect(screen.getByText('Boleta N° 120')).toBeInTheDocument();
    expect(screen.getByText('Nota de crédito N° 7')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Corregir el folio de la nota de crédito del pedido #12' }));
    expect(screen.getByRole('textbox', { name: 'Folio de la nota de crédito del pedido #12' })).toHaveValue('7');
  });

  it('un pago con tarjeta muestra que basta el voucher, y un pedido sin pagar no muestra nada', () => {
    mostrar({ documento_requerido: null, documento_por_emitir: null });
    expect(screen.getByText('Voucher de pago')).toBeInTheDocument();
    cleanup();

    mostrar({ estado: 'PENDIENTE', documento_por_emitir: null });
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });
});
