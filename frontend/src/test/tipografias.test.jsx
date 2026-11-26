import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

const { getMock, patchMock } = vi.hoisted(() => ({ getMock: vi.fn(), patchMock: vi.fn() }));
vi.mock('../components/auth/axiosConfig', () => ({ default: { get: getMock, patch: patchMock } }));

import { TIPOGRAFIAS, aplicarTipografia, obtenerTipografia } from '../constants/tipografias';

const variable = (nombre) => document.documentElement.style.getPropertyValue(nombre);

describe('Tipografías (RF-01.2)', () => {
  it('ofrece 5 combinaciones con los IDs 1 a 5 que guarda el backend', () => {
    expect(TIPOGRAFIAS.map(({ id }) => id)).toEqual([1, 2, 3, 4, 5]);
    for (const { titulos, texto } of TIPOGRAFIAS) {
      // El ajuste de tamaño mantiene las proporciones del diseño: nunca más de un 20% de diferencia
      expect(titulos.ajuste).toBeGreaterThanOrEqual(0.8);
      expect(texto.ajuste).toBeLessThanOrEqual(1.2);
    }
  });

  it('cada combinación usa una fuente de títulos distinta, para que se diferencien a simple vista', () => {
    const titulos = TIPOGRAFIAS.map(({ titulos }) => titulos.fuente);
    expect(new Set(titulos).size).toBe(TIPOGRAFIAS.length);
    expect(TIPOGRAFIAS.map(({ nombre }) => nombre)).toEqual(['Editorial', 'Urbana', 'Moderna', 'Minimalista', 'Cercana']);
  });

  it('un ID desconocido usa la Editorial', () => {
    expect(obtenerTipografia(9).nombre).toBe('Editorial');
    expect(obtenerTipografia('abc').nombre).toBe('Editorial');
  });

  it('cambia las fuentes de títulos y texto de toda la página, con fuentes de respaldo', () => {
    aplicarTipografia(1);
    expect(variable('--fuente-titulos')).toBe('"Tienda Titulos 1", Georgia, \'Times New Roman\', serif');

    // Fredoka (Cercana) no tiene serifas: su respaldo es una sans del sistema
    aplicarTipografia(5);
    expect(variable('--fuente-titulos')).toMatch(/^"Tienda Titulos 5", system-ui/);
    expect(variable('--fuente-texto')).toMatch(/^"Tienda Texto 5", system-ui/);
  });
});

describe('TipografiaSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    getMock.mockResolvedValue({ data: { tipografia_seleccionada: 2 } });
    patchMock.mockResolvedValue({ data: {} });
  });

  afterEach(() => cleanup());

  async function renderSelector() {
    // La configuración se guarda en el módulo: cada test parte limpio
    vi.resetModules();
    const { default: TipografiaSelector } = await import('../components/TipografiaSelector');
    return render(<TipografiaSelector />);
  }

  it('marca la guardada y solo deja guardar si se elige otra', async () => {
    await renderSelector();

    expect(await screen.findByRole('button', { name: /Urbana/, pressed: true })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Guardar tipografía' })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: /Cercana/ }));

    expect(screen.getByRole('button', { name: /Cercana/, pressed: true })).toBeInTheDocument();
    expect(variable('--fuente-titulos')).toMatch(/^"Tienda Titulos 5"/);
    expect(screen.getByRole('button', { name: 'Guardar tipografía' })).toBeEnabled();
  });

  it('guarda la elegida en el servidor y avisa que ya se ve en la tienda', async () => {
    await renderSelector();
    await screen.findByRole('button', { name: /Urbana/, pressed: true });
    getMock.mockResolvedValue({ data: { tipografia_seleccionada: 4 } });

    fireEvent.click(screen.getByRole('button', { name: /Minimalista/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Guardar tipografía' }));

    await waitFor(() => expect(patchMock).toHaveBeenCalledWith(
      'configuracion/negocio/', { tipografia_seleccionada: 4 }));
    expect(await screen.findByRole('status')).toHaveTextContent('Tipografía guardada');
    expect(localStorage.getItem('ecommerce_tipografia')).toBe('4');
  });

  it('si el servidor falla, avisa sin dar por guardado el cambio', async () => {
    patchMock.mockRejectedValue(new Error('sin conexión'));
    await renderSelector();
    await screen.findByRole('button', { name: /Urbana/, pressed: true });

    fireEvent.click(screen.getByRole('button', { name: /Moderna/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Guardar tipografía' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo guardar');
    expect(localStorage.getItem('ecommerce_tipografia')).toBeNull();
  });
});
