import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import IndiceConfiguracion from '../components/IndiceConfiguracion';

const GRUPOS = [
  { id: 'g1', titulo: 'Apariencia', secciones: [{ id: 's1', titulo: 'Paleta' }, { id: 's2', titulo: 'Tipografía' }] },
  { id: 'g2', titulo: 'Pagos', secciones: [{ id: 's3', titulo: 'Medios de Pago' }] },
];

// Títulos de las secciones en la página, con la altura a la que está cada uno
let alturas;
function pagina() {
  for (const id of ['s1', 's2', 's3']) {
    const titulo = document.createElement('h4');
    titulo.id = id;
    titulo.getBoundingClientRect = () => ({ top: alturas[id] });
    document.body.appendChild(titulo);
  }
}

async function desplazar(nuevas) {
  alturas = nuevas;
  await act(async () => { window.dispatchEvent(new Event('scroll')); });
}

beforeEach(() => {
  alturas = { s1: 100, s2: 900, s3: 1800 };
  pagina();
  // Como en el navegador, el cuadro siguiente corre después de devolver su id (aquí, en la siguiente microtarea)
  vi.spyOn(window, 'requestAnimationFrame').mockImplementation(fn => { queueMicrotask(() => fn()); return 1; });
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); document.body.innerHTML = ''; });

const actual = () => screen.getAllByRole('button').filter(b => b.getAttribute('aria-current') === 'location')
  .map(b => b.textContent);

it('muestra los grupos con sus secciones y marca la primera al empezar', () => {
  render(<IndiceConfiguracion grupos={GRUPOS} alElegir={vi.fn()} />);
  expect(screen.getByRole('navigation', { name: 'Secciones de configuración' })).toBeInTheDocument();
  expect(screen.getByRole('list', { name: 'Pagos' })).toBeInTheDocument();
  expect(actual()).toEqual(['Paleta']);
});

it('al bajar marca la última sección cuyo título pasó la línea de lectura', async () => {
  render(<IndiceConfiguracion grupos={GRUPOS} alElegir={vi.fn()} />);
  await desplazar({ s1: -800, s2: 60, s3: 900 });
  expect(actual()).toEqual(['Tipografía']);
  await desplazar({ s1: -1600, s2: -700, s3: 100 });
  expect(actual()).toEqual(['Medios de Pago']);
});

it('al llegar al final de la página marca la última sección aunque su título no haya subido', async () => {
  render(<IndiceConfiguracion grupos={GRUPOS} alElegir={vi.fn()} />);
  vi.spyOn(document.documentElement, 'scrollHeight', 'get').mockReturnValue(window.innerHeight + 500);
  vi.spyOn(window, 'scrollY', 'get').mockReturnValue(500);
  await desplazar({ s1: -800, s2: 60, s3: 400 });
  expect(actual()).toEqual(['Medios de Pago']);
});

it('al elegir una sección la marca y pide ir a ella', () => {
  const alElegir = vi.fn();
  render(<IndiceConfiguracion grupos={GRUPOS} alElegir={alElegir} />);
  fireEvent.click(screen.getByRole('button', { name: 'Medios de Pago' }));
  expect(alElegir).toHaveBeenCalledWith('s3');
  expect(actual()).toEqual(['Medios de Pago']);
});

it('deja de escuchar el desplazamiento al cerrarse', () => {
  const quitar = vi.spyOn(window, 'removeEventListener');
  const { unmount } = render(<IndiceConfiguracion grupos={GRUPOS} alElegir={vi.fn()} />);
  unmount();
  expect(quitar).toHaveBeenCalledWith('scroll', expect.any(Function));
});
