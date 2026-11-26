import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), patch: vi.fn() } }));
vi.mock('../hooks/useConfiguracionTienda', () => ({ recargarConfiguracion: vi.fn() }));

import clienteAxios from '../components/auth/axiosConfig';
import { recargarConfiguracion } from '../hooks/useConfiguracionTienda';
import GestorPresentacion from '../components/GestorPresentacion';

const APAGADAS = { fotos_completas: false, ficha_horizontal: false, logo_grande: false };
const casilla = (nombre) => screen.findByRole('checkbox', { name: nombre });

// Pedido de un cliente: fotos sin recorte, ficha horizontal y logo más grande, cada una por separado
describe('GestorPresentacion', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clienteAxios.get.mockResolvedValue({ data: { nombre_tienda: 'Taller', ...APAGADAS } });
  });

  afterEach(() => cleanup());

  it('parte con las tres opciones apagadas y explica cada una', async () => {
    render(<GestorPresentacion />);

    const fotos = await casilla('Mostrar las fotos completas, sin recortar');
    expect(fotos).not.toBeChecked();
    expect(fotos).toHaveAccessibleDescription(/cada foto se ve entera dentro de su marco/);
    expect(await casilla('Ficha del producto con la foto horizontal y más grande')).not.toBeChecked();
    expect(await casilla('Logo más grande')).toHaveAccessibleDescription(/en el computador, la tablet y el celular/);
  });

  it('guarda solo las opciones marcadas y recarga la tienda', async () => {
    clienteAxios.patch.mockImplementation((_, datos) => Promise.resolve({ data: { ...APAGADAS, ...datos } }));
    render(<GestorPresentacion />);

    fireEvent.click(await casilla('Mostrar las fotos completas, sin recortar'));
    fireEvent.click(await casilla('Logo más grande'));
    fireEvent.click(screen.getByRole('button', { name: 'Guardar fotos y logo' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Opciones guardadas');
    expect(clienteAxios.patch).toHaveBeenCalledWith('configuracion/negocio/',
      { fotos_completas: true, ficha_horizontal: false, logo_grande: true });
    expect(recargarConfiguracion).toHaveBeenCalled();
  });

  it('muestra lo que la tienda tiene guardado y se puede apagar', async () => {
    clienteAxios.get.mockResolvedValue({ data: { ...APAGADAS, ficha_horizontal: true } });
    clienteAxios.patch.mockImplementation((_, datos) => Promise.resolve({ data: datos }));
    render(<GestorPresentacion />);

    const ficha = await casilla('Ficha del producto con la foto horizontal y más grande');
    expect(ficha).toBeChecked();
    fireEvent.click(ficha);
    fireEvent.click(screen.getByRole('button', { name: 'Guardar fotos y logo' }));

    await screen.findByRole('status');
    expect(clienteAxios.patch).toHaveBeenCalledWith('configuracion/negocio/', APAGADAS);
  });

  it('avisa si no se pudo guardar y no da por guardado el cambio', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    clienteAxios.patch.mockRejectedValue(new Error('sin conexión'));
    render(<GestorPresentacion />);

    fireEvent.click(await casilla('Logo más grande'));
    fireEvent.click(screen.getByRole('button', { name: 'Guardar fotos y logo' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudieron guardar las opciones');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(recargarConfiguracion).not.toHaveBeenCalled();
  });
});
