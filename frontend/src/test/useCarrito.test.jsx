
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import useCarrito from '../hooks/useCarrito';

describe('useCarrito', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('devuelve un arreglo vacío si no hay carrito guardado', () => {
    const { result } = renderHook(() => useCarrito());

    expect(result.current).toEqual([]);
  });

  it('lee los productos guardados en localStorage', () => {
    localStorage.setItem(
      'carrito_local',
      JSON.stringify([
        { id: 'p1', precio: 1500, cantidad: 2 },
      ]),
    );

    const { result } = renderHook(() => useCarrito());

    expect(result.current).toEqual([
      { id: 'p1', precio: 1500, cantidad: 2 },
    ]);
  });

  it('actualiza el resultado al recibir carritoActualizado', () => {
    const { result } = renderHook(() => useCarrito());

    act(() => {
      localStorage.setItem(
        'carrito_local',
        JSON.stringify([
          { id: 'p1', precio: 2000, cantidad: 1 },
        ]),
      );
      window.dispatchEvent(new Event('carritoActualizado'));
    });

    expect(result.current).toEqual([
      { id: 'p1', precio: 2000, cantidad: 1 },
    ]);
  });

  it('actualiza el resultado cuando storage informa un cambio del carrito', () => {
    const { result } = renderHook(() => useCarrito());

    act(() => {
      localStorage.setItem(
        'carrito_local',
        JSON.stringify([
          { id: 'p2', precio: 3500, cantidad: 3 },
        ]),
      );

      window.dispatchEvent(new StorageEvent('storage', {
        key: 'carrito_local',
        newValue: JSON.stringify([
          { id: 'p2', precio: 3500, cantidad: 3 },
        ]),
        storageArea: localStorage,
      }));
    });

    expect(result.current).toEqual([
      { id: 'p2', precio: 3500, cantidad: 3 },
    ]);
  });

  it('actualiza el resultado cuando storage informa que se limpió el almacenamiento', () => {
    localStorage.setItem(
      'carrito_local',
      JSON.stringify([
        { id: 'p1', precio: 1000, cantidad: 1 },
      ]),
    );

    const { result } = renderHook(() => useCarrito());

    act(() => {
      localStorage.removeItem('carrito_local');

      window.dispatchEvent(new StorageEvent('storage', {
        key: null,
        newValue: null,
        storageArea: localStorage,
      }));
    });

    expect(result.current).toEqual([]);
  });

  it('ignora eventos storage de otras claves', () => {
    localStorage.setItem(
      'carrito_local',
      JSON.stringify([
        { id: 'p1', precio: 1000, cantidad: 1 },
      ]),
    );

    const { result } = renderHook(() => useCarrito());

    act(() => {
      localStorage.setItem('otra_clave', 'valor');

      window.dispatchEvent(new StorageEvent('storage', {
        key: 'otra_clave',
        newValue: 'valor',
        storageArea: localStorage,
      }));
    });

    expect(result.current).toEqual([
      { id: 'p1', precio: 1000, cantidad: 1 },
    ]);
  });

  it('interpreta como vacío un carrito guardado con JSON inválido', () => {
    localStorage.setItem('carrito_local', '{json inválido');

    const { result } = renderHook(() => useCarrito());

    expect(result.current).toEqual([]);
  });

  it('deja de escuchar eventos al desmontar el hook', () => {
    const { unmount } = renderHook(() => useCarrito());

    expect(() => unmount()).not.toThrow();
  });
});
