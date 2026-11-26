import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn() } }));

import clienteAxios from '../components/auth/axiosConfig';
import ProtectedRoute from '../components/ProtectedRoute';
import { Bloque, Cargando } from '../components/carga/Esqueleto';
import { EsqueletoPanel, EsqueletoTabla } from '../components/carga/EsqueletosPanel';
import Spinner from '../components/carga/Spinner';

describe('Piezas de carga', () => {
  afterEach(() => cleanup());

  it('el esqueleto anuncia su texto y oculta los bloques al lector de pantalla', () => {
    render(
      <Cargando texto="Cargando inventario...">
        <Bloque ancho="40%" />
        <Bloque alto="2rem" forma="boton" />
      </Cargando>
    );

    const estado = screen.getByRole('status');
    expect(estado).toHaveTextContent('Cargando inventario...');
    expect(estado).not.toHaveAttribute('aria-busy');
    const bloques = estado.querySelectorAll('.esqueleto');
    expect(bloques).toHaveLength(2);
    bloques.forEach((bloque) => expect(bloque.closest('[aria-hidden="true"]')).not.toBeNull());
  });

  it('un bloque toma su tamaño y su forma', () => {
    const { container } = render(<Bloque ancho="3rem" alto="3rem" forma="circulo" />);
    const bloque = container.querySelector('.esqueleto');
    expect(bloque).toHaveClass('esqueleto--circulo');
    expect(bloque).toHaveStyle({ width: '3rem', height: '3rem' });
    expect(bloque).toHaveAttribute('aria-hidden', 'true');
  });

  it('mientras se verifica la sesión del admin se ve el panel vacío, con su contenido principal', () => {
    localStorage.setItem('access_token', 'token');
    clienteAxios.get.mockReturnValue(new Promise(() => {}));
    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route element={<ProtectedRoute allowedRoles={['ADMIN']} esqueleto={<EsqueletoPanel />} />}>
            <Route path="/admin" element={<p>Panel</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByRole('status')).toHaveTextContent('Verificando sesión...');
    expect(screen.getByRole('main')).toHaveAttribute('id', 'contenido');
    expect(document.querySelectorAll('.esqueleto').length).toBeGreaterThan(10);
    localStorage.clear();
  });

  it('una tabla del panel tiene su encabezado y las filas pedidas', () => {
    const { container } = render(<EsqueletoTabla filas={3} columnas={7} />);
    const filas = container.querySelectorAll('.esqueleto-tabla-fila');
    expect(filas).toHaveLength(4);
    expect(filas[0]).toHaveClass('esqueleto-tabla-fila--encabezado');
    expect(filas[1].querySelectorAll('.esqueleto')).toHaveLength(7);
  });

  it('el spinner no cambia el nombre del botón', () => {
    render(<button type="submit" disabled><Spinner />Guardando...</button>);
    expect(screen.getByRole('button', { name: 'Guardando...' })).toBeInTheDocument();
  });
});
