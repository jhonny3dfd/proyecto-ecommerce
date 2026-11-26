import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), patch: vi.fn() } }));
vi.mock('../hooks/useConfiguracionTienda', () => ({ recargarConfiguracion: vi.fn() }));

import clienteAxios from '../components/auth/axiosConfig';
import { recargarConfiguracion } from '../hooks/useConfiguracionTienda';
import GestorBlog from '../components/GestorBlog';

const CONFIGURACION = { blog_activo: false, blog_nombre: 'Nosotros' };

describe('GestorBlog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clienteAxios.get.mockResolvedValue({ data: CONFIGURACION });
  });

  afterEach(() => cleanup());

  it('parte desactivado y con el nombre por defecto', async () => {
    render(<GestorBlog />);

    expect(await screen.findByRole('checkbox', { name: 'Mostrar el blog en mi tienda' })).not.toBeChecked();
    expect(screen.getByLabelText('Nombre en el menú')).toHaveValue('Nosotros');
  });

  it('el admin lo activa con otro nombre y la tienda se actualiza', async () => {
    clienteAxios.patch.mockImplementation((_, datos) => Promise.resolve({ data: { ...CONFIGURACION, ...datos } }));
    render(<GestorBlog />);

    fireEvent.click(await screen.findByRole('checkbox', { name: 'Mostrar el blog en mi tienda' }));
    fireEvent.change(screen.getByLabelText('Nombre en el menú'), { target: { value: 'Portafolio' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar blog' }));

    expect(await screen.findByRole('status')).toHaveTextContent('ya ven "Portafolio" en el menú');
    expect(clienteAxios.patch).toHaveBeenCalledWith('configuracion/negocio/',
      { blog_activo: true, blog_nombre: 'Portafolio' });
    expect(recargarConfiguracion).toHaveBeenCalled();
  });

  it('al desactivarlo avisa que el menú vuelve a la sección Nosotros', async () => {
    clienteAxios.get.mockResolvedValue({ data: { blog_activo: true, blog_nombre: 'Blog' } });
    clienteAxios.patch.mockImplementation((_, datos) => Promise.resolve({ data: datos }));
    render(<GestorBlog />);

    fireEvent.click(await screen.findByRole('checkbox', { name: 'Mostrar el blog en mi tienda' }));
    fireEvent.click(screen.getByRole('button', { name: 'Guardar blog' }));

    expect(await screen.findByRole('status')).toHaveTextContent('vuelve a llevar a la sección Nosotros');
  });

  it('muestra junto al campo el error que devuelve el servidor', async () => {
    clienteAxios.patch.mockRejectedValue({
      response: { data: { blog_nombre: ['El nombre del menú puede tener hasta 30 caracteres.'] } }
    });
    render(<GestorBlog />);

    fireEvent.click(await screen.findByRole('button', { name: 'Guardar blog' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Revisa los datos marcados.');
    const campo = screen.getByLabelText('Nombre en el menú');
    expect(campo).toHaveAttribute('aria-invalid', 'true');
    expect(campo).toHaveAccessibleDescription(/hasta 30 caracteres/);
  });

  it('avisa si no pudo cargar la configuración', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    clienteAxios.get.mockRejectedValue(new Error('sin red'));
    render(<GestorBlog />);

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo cargar la configuración del blog.');
  });
});
