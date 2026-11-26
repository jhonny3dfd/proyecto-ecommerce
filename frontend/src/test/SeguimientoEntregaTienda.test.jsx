import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock('../components/header/header', () => ({ default: () => null }));

import clienteAxios from '../components/auth/axiosConfig';
import SeguimientoEnvio from '../pages/SeguimientoEnvio';

async function consultar(respuesta) {
  clienteAxios.post.mockResolvedValue({ data: respuesta });
  render(<MemoryRouter><SeguimientoEnvio /></MemoryRouter>);
  fireEvent.change(screen.getByLabelText(/Número de orden/), { target: { value: '42' } });
  fireEvent.change(screen.getByLabelText(/Correo/), { target: { value: 'ana@example.test' } });
  fireEvent.click(screen.getByRole('button', { name: 'Consultar seguimiento' }));
  return screen.findByRole('region', { name: 'Pedido #42' });
}

describe('Seguimiento de pedido (RF-02.4)', () => {
  beforeEach(() => vi.clearAllMocks());

  afterEach(() => cleanup());

  it('con courier muestra el código y la línea de tiempo', async () => {
    const resultado = await consultar({
      numero_orden: 42, proveedor: 'CHILEXPRESS', codigo_seguimiento: '712678903156', estado_actual: 'En tránsito',
      linea_tiempo_estandar: ['En origen', 'En tránsito', 'En reparto', 'Entregado']
    });

    expect(within(resultado).getByText('712678903156')).toBeInTheDocument();
    expect(within(resultado).getByRole('list')).toBeInTheDocument();
    expect(within(resultado).getByText('En tránsito', { selector: '.seguimiento-paso-nombre' }))
      .toBeInTheDocument();
  });

  it('con entrega coordinada muestra las instrucciones, sin código ni pasos de courier', async () => {
    const resultado = await consultar({
      numero_orden: 42, entrega_de_la_tienda: true, proveedor: 'Entrega coordinada',
      estado_actual: 'La tienda coordinará la entrega contigo', instrucciones: 'Te escribimos por WhatsApp.',
      codigo_seguimiento: null, linea_tiempo_estandar: []
    });

    expect(within(resultado).getByText('Entrega coordinada')).toBeInTheDocument();
    expect(within(resultado).getByText('La tienda coordinará la entrega contigo')).toBeInTheDocument();
    expect(within(resultado).getByRole('heading', { name: 'Cómo recibes tu pedido' })).toBeInTheDocument();
    expect(within(resultado).getByText('Te escribimos por WhatsApp.')).toBeInTheDocument();
    expect(within(resultado).queryByText('Código de seguimiento')).not.toBeInTheDocument();
    expect(within(resultado).queryByText('Proveedor no soportado')).not.toBeInTheDocument();
    expect(within(resultado).queryByRole('list')).not.toBeInTheDocument();
  });
});
