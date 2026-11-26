
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../components/auth/axiosConfig', () => ({
  default: { get: vi.fn() }
}));

vi.mock('../hooks/useConfiguracionTienda', () => ({
  default: vi.fn()
}));

vi.mock('../components/header/header', () => ({
  default: () => <div>Header simulado</div>
}));

import clienteAxios from '../components/auth/axiosConfig';
import useConfiguracionTienda from '../hooks/useConfiguracionTienda';
import SobreMi from '../pages/SobreMi';

const DATOS = {
  nombre: 'Mi historia',
  biografia: '<h2>Nuestra historia</h2><p>Productos hechos a mano.</p>',
  proyectos: [
    {
      slug: 'proyecto-a',
      titulo: 'Proyecto A',
      resumen: 'Primer proyecto',
      portada: null
    },
    {
      slug: 'proyecto-b',
      titulo: 'Proyecto B',
      resumen: 'Segundo proyecto',
      portada: null
    }
  ],
  contacto: {
    correo: 'contacto@ejemplo.cl',
    telefono: '+56 9 1234 5678',
    instagram: '@miemprendimiento'
  }
};

const renderizar = () => render(
  <MemoryRouter>
    <SobreMi />
  </MemoryRouter>
);

describe('SobreMi - página pública', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    useConfiguracionTienda.mockReturnValue({
      nombre_tienda: 'Tienda de prueba',
      blog_activo: true
    });

    clienteAxios.get.mockResolvedValue({
      data: { ...DATOS }
    });
  });

  afterEach(() => {
    cleanup();
    document.title = '';
  });

  it('carga la página y muestra el nombre configurado', async () => {
    renderizar();

    expect(await screen.findByRole('heading', {
      level: 1,
      name: 'Mi historia'
    })).toBeInTheDocument();

    expect(screen.getByText('Tienda de prueba')).toBeInTheDocument();

    expect(clienteAxios.get)
      .toHaveBeenCalledWith('ventas/sobre-mi/');
  });

  it('muestra la biografía conservando su formato HTML', async () => {
    renderizar();

    const seccion = await screen.findByRole('region', {
      name: 'Nuestra historia'
    });

    expect(within(seccion).getByRole('heading', {
      level: 2,
      name: 'Nuestra historia'
    })).toBeInTheDocument();

    expect(within(seccion).getByText('Productos hechos a mano.'))
      .toBeInTheDocument();
  });

  it('muestra los proyectos destacados en el orden recibido', async () => {
    renderizar();

    const seccion = await screen.findByRole('region', {
      name: 'Proyectos destacados'
    });

    const enlaces = within(seccion).getAllByRole('link');

    expect(enlaces.map((enlace) => enlace.textContent))
      .toEqual(['Proyecto A', 'Proyecto B']);

    expect(enlaces[0]).toHaveAttribute('href', '/blog/proyecto-a');
    expect(enlaces[1]).toHaveAttribute('href', '/blog/proyecto-b');
  });

  it('no enlaza los proyectos cuando el blog está desactivado', async () => {
    useConfiguracionTienda.mockReturnValue({
      nombre_tienda: 'Tienda de prueba',
      blog_activo: false
    });

    renderizar();

    const seccion = await screen.findByRole('region', {
      name: 'Proyectos destacados'
    });

    expect(within(seccion).getByText('Proyecto A'))
      .toBeInTheDocument();

    expect(within(seccion).queryByRole('link'))
      .not.toBeInTheDocument();
  });

  it('muestra los contactos con sus enlaces correctos', async () => {
    renderizar();

    const seccion = await screen.findByRole('region', {
      name: 'Contacto'
    });

    expect(within(seccion).getByRole('link', {
      name: 'contacto@ejemplo.cl'
    })).toHaveAttribute('href', 'mailto:contacto@ejemplo.cl');

    expect(within(seccion).getByRole('link', {
      name: '+56 9 1234 5678'
    })).toHaveAttribute('href', 'tel:+56912345678');

    expect(within(seccion).getByRole('link', {
      name: '@miemprendimiento'
    })).toHaveAttribute(
      'href',
      'https://www.instagram.com/miemprendimiento/'
    );
  });

  it('oculta proyectos y contactos cuando no hay información', async () => {
    clienteAxios.get.mockResolvedValue({
      data: {
        nombre: 'Mi historia',
        biografia: '',
        proyectos: [],
        contacto: {
          correo: '',
          telefono: '',
          instagram: ''
        }
      }
    });

    renderizar();

    expect(await screen.findByRole('heading', {
      name: 'Mi historia'
    })).toBeInTheDocument();

    expect(screen.queryByRole('heading', {
      name: 'Proyectos destacados'
    })).not.toBeInTheDocument();

    expect(screen.queryByRole('heading', {
      name: 'Contacto'
    })).not.toBeInTheDocument();
  });

  it('muestra página no disponible cuando el backend devuelve 404', async () => {
    clienteAxios.get.mockRejectedValue({
      response: { status: 404 }
    });

    renderizar();

    expect(await screen.findByRole('heading', {
      name: 'Esta página no está disponible'
    })).toBeInTheDocument();

    expect(screen.getByRole('link', {
      name: 'Ir al inicio'
    })).toHaveAttribute('href', '/');
  });

  it('muestra un aviso cuando ocurre un error de conexión', async () => {
    clienteAxios.get.mockRejectedValue(new Error('Sin conexión'));

    renderizar();

    expect(await screen.findByRole('alert'))
      .toHaveTextContent('No pudimos cargar esta página');

    expect(screen.getByText(
      'Revisa tu conexión e inténtalo nuevamente.'
    )).toBeInTheDocument();
  });
});
