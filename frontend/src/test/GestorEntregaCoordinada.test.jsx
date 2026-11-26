import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), patch: vi.fn() } }));
vi.mock('../hooks/useConfiguracionTienda', () => ({ recargarConfiguracion: vi.fn() }));

import clienteAxios from '../components/auth/axiosConfig';
import GestorEntregaCoordinada from '../components/GestorEntregaCoordinada';

const CONFIGURACION = {
  entrega_coordinada_activa: false, costo_entrega_coordinada: 0, instrucciones_entrega_coordinada: ''
};

describe('GestorEntregaCoordinada (RF-02.3)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clienteAxios.get.mockResolvedValue({ data: CONFIGURACION });
  });

  afterEach(() => cleanup());

  it('el admin la activa con su costo e instrucciones', async () => {
    clienteAxios.patch.mockImplementation((_, datos) => Promise.resolve({ data: { ...CONFIGURACION, ...datos } }));
    render(<GestorEntregaCoordinada />);

    fireEvent.click(await screen.findByRole('checkbox', { name: /ofrecer "entrega coordinada"/i }));
    fireEvent.change(screen.getByLabelText('Costo de la entrega (CLP)'), { target: { value: '2500' } });
    fireEvent.change(screen.getByLabelText('Instrucciones para el comprador'),
      { target: { value: 'Te escribimos por WhatsApp.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar entrega coordinada' }));

    expect(await screen.findByRole('status')).toHaveTextContent('tus clientes ya la ven al comprar');
    expect(clienteAxios.patch).toHaveBeenCalledWith('configuracion/negocio/', {
      entrega_coordinada_activa: true, costo_entrega_coordinada: 2500,
      instrucciones_entrega_coordinada: 'Te escribimos por WhatsApp.'
    });
  });

  it('un costo vacío se guarda como entrega gratis', async () => {
    clienteAxios.patch.mockImplementation((_, datos) => Promise.resolve({ data: { ...CONFIGURACION, ...datos } }));
    render(<GestorEntregaCoordinada />);

    fireEvent.change(await screen.findByLabelText('Costo de la entrega (CLP)'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar entrega coordinada' }));

    await waitFor(() => expect(clienteAxios.patch).toHaveBeenCalledWith('configuracion/negocio/',
      expect.objectContaining({ costo_entrega_coordinada: 0 })));
  });

  it('muestra junto al campo el error que devuelve el servidor', async () => {
    // Un costo negativo ya lo frena el navegador (min=0); aquí lo rechaza el servidor
    clienteAxios.patch.mockRejectedValue({
      response: { data: { costo_entrega_coordinada: ['Asegúrese de que este valor es menor o igual a 1000000.'] } }
    });
    render(<GestorEntregaCoordinada />);

    fireEvent.change(await screen.findByLabelText('Costo de la entrega (CLP)'), { target: { value: '2500' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar entrega coordinada' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Revisa los datos marcados.');
    const campo = screen.getByLabelText('Costo de la entrega (CLP)');
    expect(campo).toHaveAttribute('aria-invalid', 'true');
    expect(campo).toHaveAccessibleDescription(/menor o igual a 1000000/);
  });
});
