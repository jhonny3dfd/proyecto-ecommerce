import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import BotonSubir from '../components/BotonSubir';

let posicion;
beforeEach(() => {
  posicion = 0;
  vi.spyOn(window, 'scrollY', 'get').mockImplementation(() => posicion);
  vi.spyOn(window, 'requestAnimationFrame').mockImplementation(fn => { queueMicrotask(() => fn()); return 1; });
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

async function bajarA(y) {
  posicion = y;
  await act(async () => { window.dispatchEvent(new Event('scroll')); });
}

const boton = () => screen.queryByRole('button', { name: 'Volver al inicio de la página' });

function mostrar() {
  return render(<><main id="contenido" tabIndex={-1}>Catálogo</main><BotonSubir destino="contenido" /></>);
}

it('no aparece arriba de la página', () => {
  mostrar();
  expect(boton()).toBeNull();
});

it('aparece al bajar más de 400 píxeles y desaparece al volver arriba', async () => {
  mostrar();
  await bajarA(300);
  expect(boton()).toBeNull();
  await bajarA(401);
  expect(boton()).toBeInTheDocument();
  await bajarA(100);
  expect(boton()).toBeNull();
});

it('aparece de inmediato si la página ya se abrió más abajo', () => {
  posicion = 1200;
  mostrar();
  expect(boton()).toBeInTheDocument();
});

it('al pulsarlo sube con suavidad y deja el foco al inicio del contenido', async () => {
  mostrar();
  await bajarA(1500);
  fireEvent.click(boton());
  expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' });
  expect(document.getElementById('contenido')).toHaveFocus();
});

it('sube sin animación si el visitante pidió reducir el movimiento', async () => {
  vi.stubGlobal('matchMedia', (consulta) => ({ matches: consulta.includes('reduced-motion') }));
  mostrar();
  await bajarA(1500);
  fireEvent.click(boton());
  expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'auto' });
});

it('el ícono es decorativo y el nombre del botón lo da su etiqueta', async () => {
  mostrar();
  await bajarA(1500);
  expect(boton().querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  expect(boton()).toHaveAttribute('type', 'button');
});
