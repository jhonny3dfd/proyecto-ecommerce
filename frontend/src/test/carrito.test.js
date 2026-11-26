
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { postMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
}));

vi.mock('../components/auth/axiosConfig', () => ({
  default: {
    post: postMock,
  },
}));

import {
  leerSnapshotCarrito,
  interpretarCarrito,
  validarCarrito,
  guardarCarrito,
  vaciarCarrito,
  ajustarCarrito,
} from '../components/carrito';

describe('carrito.js', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    postMock.mockResolvedValue({ data: { items: [] } });
  });

  describe('leerSnapshotCarrito', () => {
    it('lee el carrito guardado en localStorage', () => {
      localStorage.setItem('carrito_local', '[{"id":"p1"}]');

      expect(leerSnapshotCarrito()).toBe('[{"id":"p1"}]');
    });

    it('devuelve null si no existe un carrito guardado', () => {
      expect(leerSnapshotCarrito()).toBeNull();
    });
  });

  describe('interpretarCarrito', () => {
    it('interpreta y normaliza precios y cantidades numéricas', () => {
      const resultado = interpretarCarrito(
        '[{"id":"p1","precio":"1500","cantidad":"2"}]',
      );

      expect(resultado).toEqual([
        { id: 'p1', precio: 1500, cantidad: 2 },
      ]);
    });

    it('devuelve un arreglo vacío si el JSON es inválido', () => {
      expect(interpretarCarrito('{json inválido')).toEqual([]);
    });

    it('devuelve un arreglo vacío si el contenido no es un arreglo', () => {
      expect(interpretarCarrito('{"id":"p1"}')).toEqual([]);
    });

    it('descarta productos con datos inválidos', () => {
      const resultado = interpretarCarrito(JSON.stringify([
        null,
        'producto',
        { id: 'p1', precio: -1, cantidad: 1 },
        { id: 'p2', precio: 100, cantidad: 0 },
        { id: 'p3', precio: 'abc', cantidad: 1 },
        { id: 'p4', precio: 100, cantidad: 1.5 },
        { id: 'p5', precio: 0, cantidad: 1 },
      ]));

      expect(resultado).toEqual([
        { id: 'p5', precio: 0, cantidad: 1 },
      ]);
    });
  });

  describe('validarCarrito', () => {
    it('envía al backend los identificadores, variantes y cantidades', async () => {
      const items = [
        { id: 'mongo-1', sku: 'SKU-1', cantidad: 2 },
      ];
      postMock.mockResolvedValue({
        data: { items: [{ disponible: 2 }] },
      });

      const resultado = await validarCarrito(items);

      expect(postMock).toHaveBeenCalledWith('ventas/carrito/validar/', {
        items: [{
          producto_mongo_id: 'mongo-1',
          variante_sku: 'SKU-1',
          cantidad: 2,
        }],
      });
      expect(resultado).toEqual({ items: [{ disponible: 2 }] });
    });

    it('propaga los errores del backend', async () => {
      postMock.mockRejectedValue(new Error('Error de validación'));

      await expect(validarCarrito([])).rejects.toThrow(
        'Error de validación',
      );
    });
  });

  describe('guardarCarrito', () => {
    it('guarda el carrito local y emite el evento de actualización', async () => {
      const listener = vi.fn();
      window.addEventListener('carritoActualizado', listener);

      await guardarCarrito([
        { id: 'p1', precio: 1000, cantidad: 1 },
      ]);

      expect(JSON.parse(localStorage.getItem('carrito_local'))).toEqual([
        { id: 'p1', precio: 1000, cantidad: 1 },
      ]);
      expect(listener).toHaveBeenCalledTimes(1);

      window.removeEventListener('carritoActualizado', listener);
    });

    it('no emite el evento si el contenido guardado es idéntico', async () => {
      const items = [{ id: 'p1', precio: 1000, cantidad: 1 }];
      localStorage.setItem('carrito_local', JSON.stringify(items));
      const listener = vi.fn();
      window.addEventListener('carritoActualizado', listener);

      await guardarCarrito(items);

      expect(listener).not.toHaveBeenCalled();

      window.removeEventListener('carritoActualizado', listener);
    });

    it('sincroniza con el backend si existe un token', async () => {
      localStorage.setItem('access_token', 'token-prueba');

      await guardarCarrito([
        { id: 'p1', precio: 1000, cantidad: 1 },
      ]);

      expect(postMock).toHaveBeenCalledWith('ventas/carrito/', {
        items: [{ id: 'p1', precio: 1000, cantidad: 1 }],
      });
    });

    it('no sincroniza con el backend si no existe un token', async () => {
      await guardarCarrito([]);

      expect(postMock).not.toHaveBeenCalled();
    });

    it('no falla si la sincronización con el backend falla', async () => {
      localStorage.setItem('access_token', 'token-prueba');
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      postMock.mockRejectedValue(new Error('Error de red'));

      await expect(guardarCarrito([
        { id: 'p1', precio: 1000, cantidad: 1 },
      ])).resolves.toBeUndefined();

      expect(errorSpy).toHaveBeenCalled();
      errorSpy.mockRestore();
    });
  });

  describe('vaciarCarrito', () => {
    it('elimina el carrito local y emite el evento', async () => {
      localStorage.setItem('carrito_local', '[{"id":"p1"}]');
      const listener = vi.fn();
      window.addEventListener('carritoActualizado', listener);

      await vaciarCarrito();

      expect(localStorage.getItem('carrito_local')).toBeNull();
      expect(listener).toHaveBeenCalledTimes(1);

      window.removeEventListener('carritoActualizado', listener);
    });

    it('sincroniza el carrito vacío si existe un token', async () => {
      localStorage.setItem('access_token', 'token-prueba');

      await vaciarCarrito();

      expect(postMock).toHaveBeenCalledWith('ventas/carrito/', {
        items: [],
      });
    });
  });

  describe('ajustarCarrito', () => {
    const producto = {
      id: 'p1',
      sku: 'SKU-1',
      nombre: 'Producto de prueba',
      precio: 1000,
      cantidad: 3,
    };

    it('conserva los productos que no aparecen en la revisión', () => {
      const resultado = ajustarCarrito([producto], { items: [] });

      expect(resultado.items).toEqual([producto]);
      expect(resultado.avisos).toEqual([]);
    });

    it.each(['NO_DISPONIBLE', 'SIN_STOCK'])(
      'elimina el producto cuando el problema es %s',
      (problema) => {
        const resultado = ajustarCarrito([producto], {
          items: [{
            producto_mongo_id: 'p1',
            variante_sku: 'SKU-1',
            problema,
            mensaje: 'Producto no disponible.',
          }],
        });

        expect(resultado.items).toEqual([]);
        expect(resultado.avisos).toEqual([
          'Producto no disponible. Lo quitamos de tu carrito.',
        ]);
      },
    );

    it('reduce la cantidad al stock disponible', () => {
      const resultado = ajustarCarrito([producto], {
        items: [{
          producto_mongo_id: 'p1',
          variante_sku: 'SKU-1',
          problema: 'STOCK_INSUFICIENTE',
          mensaje: 'Stock limitado.',
          disponible: 2,
          precio: 1000,
          nombre: 'Producto de prueba',
        }],
      });

      expect(resultado.items[0].cantidad).toBe(2);
      expect(resultado.avisos).toContain(
        'Stock limitado. Ajustamos la cantidad.',
      );
    });

    it('actualiza el precio y agrega un aviso si cambió', () => {
      const resultado = ajustarCarrito([producto], {
        items: [{
          producto_mongo_id: 'p1',
          variante_sku: 'SKU-1',
          problema: null,
          mensaje: '',
          disponible: 3,
          precio: 2500,
          nombre: 'Producto de prueba',
        }],
      });

      expect(resultado.items[0].precio).toBe(2500);
      expect(resultado.avisos).toContain(
        'El precio de Producto de prueba cambió a $2.500.',
      );
    });

    it('ajusta la cantidad y el precio en una misma revisión', () => {
      const resultado = ajustarCarrito([producto], {
        items: [{
          producto_mongo_id: 'p1',
          variante_sku: 'SKU-1',
          problema: 'STOCK_INSUFICIENTE',
          mensaje: 'Stock limitado.',
          disponible: 2,
          precio: 2500,
          nombre: 'Producto de prueba',
        }],
      });

      expect(resultado.items[0]).toMatchObject({
        cantidad: 2,
        precio: 2500,
      });
      expect(resultado.avisos).toHaveLength(2);
    });
  });
});
