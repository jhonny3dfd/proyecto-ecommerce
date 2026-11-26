import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { Link, MemoryRouter, Route, Routes, useNavigate, useSearchParams } from 'react-router-dom';
import AccesibilidadNavegacion from '../components/AccesibilidadNavegacion';

vi.mock('../hooks/useConfiguracionTienda', () => ({ default: () => ({ nombre_tienda: 'Tienda QA' }) }));

function Volver() {
  const navegar = useNavigate();
  return <button type="button" onClick={() => navegar(-1)}>Volver</button>;
}

function Catalogo() {
  const [, setParametros] = useSearchParams();
  return <button type="button" onClick={() => setParametros({ page: '2' })}>Página 2</button>;
}

function mostrar(inicio = '/') {
  return render(
    <MemoryRouter initialEntries={[inicio]}>
      <AccesibilidadNavegacion />
      <main tabIndex={-1}>
        <Link to="/blog">Blog</Link>
        <Link to="/#nosotros">Nosotros</Link>
        <Link to="/catalogo">Catálogo</Link>
        <Volver />
        <Routes>
          <Route path="/" element={<p>Landing</p>} />
          <Route path="/blog" element={<p>Blog</p>} />
          <Route path="/catalogo" element={<Catalogo />} />
        </Routes>
      </main>
    </MemoryRouter>
  );
}

let desplazar;
beforeEach(() => { desplazar = vi.spyOn(window, 'scrollTo').mockImplementation(() => {}); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('al entrar a otra página la muestra desde arriba', () => {
  mostrar();
  fireEvent.click(screen.getByRole('link', { name: 'Blog' }));
  expect(screen.getByText('Blog', { selector: 'p' })).toBeInTheDocument();
  expect(desplazar).toHaveBeenCalledWith(0, 0);
});

it('no mueve la página al cargar la primera vez', () => {
  mostrar();
  expect(desplazar).not.toHaveBeenCalled();
});

it('con Atrás deja que el navegador recupere la posición anterior', () => {
  mostrar();
  fireEvent.click(screen.getByRole('link', { name: 'Blog' }));
  desplazar.mockClear();
  fireEvent.click(screen.getByRole('button', { name: 'Volver' }));
  expect(screen.getByText('Landing')).toBeInTheDocument();
  expect(desplazar).not.toHaveBeenCalled();
});

it('un enlace con ancla no sube al inicio: la landing baja a su sección', () => {
  mostrar('/blog');
  fireEvent.click(screen.getByRole('link', { name: 'Nosotros' }));
  expect(screen.getByText('Landing')).toBeInTheDocument();
  expect(desplazar).not.toHaveBeenCalled();
});

it('cambiar de página o filtro en el catálogo no sube al inicio', () => {
  mostrar('/catalogo');
  fireEvent.click(screen.getByRole('button', { name: 'Página 2' }));
  expect(desplazar).not.toHaveBeenCalled();
});
