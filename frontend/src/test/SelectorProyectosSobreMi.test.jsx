
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';

vi.mock('../components/auth/axiosConfig', () => ({
  default: { get: vi.fn(), put: vi.fn() }
}));

import clienteAxios from '../components/auth/axiosConfig';
import SelectorProyectosSobreMi from '../components/SelectorProyectosSobreMi';

const PUBLICACIONES = [
  { id: 1, titulo: 'Proyecto A', estado: 'PUBLICADA' },
  { id: 2, titulo: 'Proyecto B', estado: 'PUBLICADA' },
  { id: 3, titulo: 'Proyecto C', estado: 'BORRADOR' }
];

const prepararCarga = (proyectos = [1, 2]) => {
  clienteAxios.get.mockImplementation((url) => {
    if (url === 'ventas/admin/blog/') {
      return Promise.resolve({ data: PUBLICACIONES });
    }

    if (url === 'ventas/admin/sobre-mi/proyectos/') {
      return Promise.resolve({ data: { proyectos } });
    }

    return Promise.reject(new Error('Ruta inesperada'));
  });
};

describe('SelectorProyectosSobreMi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    prepararCarga();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('avisa que los proyectos no se muestran con el blog apagado, y permite elegirlos igual', async () => {
    const { rerender } = render(<SelectorProyectosSobreMi blogActivo={false} />);

    expect(await screen.findByText(/El blog está apagado: los proyectos no se mostrarán/)).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /Proyecto A/ })).toBeEnabled();

    rerender(<SelectorProyectosSobreMi blogActivo />);
    expect(screen.queryByText(/El blog está apagado/)).not.toBeInTheDocument();
  });

  it('carga las publicaciones y los proyectos seleccionados', async () => {
    render(<SelectorProyectosSobreMi />);

    expect(await screen.findByRole('heading', {
      name: 'Proyectos destacados'
    })).toBeInTheDocument();

    expect(screen.getByRole('checkbox', {
      name: /Proyecto A/
    })).toBeChecked();

    expect(screen.getByRole('checkbox', {
      name: /Proyecto B/
    })).toBeChecked();

    expect(screen.getByRole('checkbox', {
      name: /Proyecto C/
    })).not.toBeChecked();

    expect(clienteAxios.get).toHaveBeenCalledWith('ventas/admin/blog/');
    expect(clienteAxios.get).toHaveBeenCalledWith(
      'ventas/admin/sobre-mi/proyectos/'
    );
  });

  it('permite seleccionar y deseleccionar publicaciones', async () => {
    clienteAxios.put.mockImplementation((_, datos) =>
      Promise.resolve({ data: datos })
    );

    render(<SelectorProyectosSobreMi />);

    fireEvent.click(await screen.findByRole('checkbox', {
      name: /Proyecto A/
    }));

    fireEvent.click(screen.getByRole('checkbox', {
      name: /Proyecto C/
    }));

    fireEvent.click(screen.getByRole('button', {
      name: 'Guardar proyectos destacados'
    }));

    await waitFor(() => {
      expect(clienteAxios.put).toHaveBeenCalledWith(
        'ventas/admin/sobre-mi/proyectos/',
        { proyectos: [2, 3] }
      );
    });

    expect(await screen.findByRole('status'))
      .toHaveTextContent('Los proyectos destacados se guardaron correctamente.');
  });

  it('permite cambiar el orden de los proyectos', async () => {
    clienteAxios.put.mockImplementation((_, datos) =>
      Promise.resolve({ data: datos })
    );

    render(<SelectorProyectosSobreMi />);

    fireEvent.click(await screen.findByRole('button', {
      name: 'Subir Proyecto B'
    }));

    const lista = screen.getByRole('list');
    const elementos = within(lista).getAllByRole('listitem');

    expect(elementos[0]).toHaveTextContent('Proyecto B');
    expect(elementos[1]).toHaveTextContent('Proyecto A');

    fireEvent.click(screen.getByRole('button', {
      name: 'Guardar proyectos destacados'
    }));

    await waitFor(() => {
      expect(clienteAxios.put).toHaveBeenCalledWith(
        'ventas/admin/sobre-mi/proyectos/',
        { proyectos: [2, 1] }
      );
    });
  });

  it('deshabilita los botones cuando no se puede mover un proyecto', async () => {
    render(<SelectorProyectosSobreMi />);

    expect(await screen.findByRole('button', {
      name: 'Subir Proyecto A'
    })).toBeDisabled();

    expect(screen.getByRole('button', {
      name: 'Bajar Proyecto B'
    })).toBeDisabled();
  });

  it('muestra un mensaje cuando no existen publicaciones', async () => {
    clienteAxios.get.mockImplementation((url) => {
      if (url === 'ventas/admin/blog/') {
        return Promise.resolve({ data: [] });
      }

      return Promise.resolve({ data: { proyectos: [] } });
    });

    render(<SelectorProyectosSobreMi />);

    expect(await screen.findByText(/Todavía no tienes publicaciones/))
      .toBeInTheDocument();
  });

  it('muestra un error cuando falla la carga', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    clienteAxios.get.mockRejectedValue(new Error('Sin conexión'));

    render(<SelectorProyectosSobreMi />);

    expect(await screen.findByRole('alert'))
      .toHaveTextContent(
        'No se pudieron cargar las publicaciones o los proyectos destacados.'
      );
  });

  it('muestra un error cuando falla el guardado', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    clienteAxios.put.mockRejectedValue(new Error('Error del servidor'));

    render(<SelectorProyectosSobreMi />);

    fireEvent.click(await screen.findByRole('button', {
      name: 'Guardar proyectos destacados'
    }));

    expect(await screen.findByRole('alert'))
      .toHaveTextContent('No se pudieron guardar los proyectos destacados.');
  });
});
