import { describe, expect, it } from 'vitest';
import { coleccionesDelInventario } from '../utils/colecciones';

describe('coleccionesDelInventario', () => {
  it('junta las colecciones de publicados y borradores sin repetir mayúsculas ni espacios', () => {
    const productos = [
      { publicado: true, colecciones: ['cyber', ' Navidad '] },
      { publicado: false, colecciones: ['Cyber', 'Solo borrador'] },
      { colecciones: ['navidad'] },
    ];
    expect(coleccionesDelInventario(productos)).toEqual(['Cyber', 'Navidad', 'Solo borrador']);
  });

  it('elige siempre la misma escritura, sin importar el orden de los productos', () => {
    const a = [{ colecciones: ['cyber'] }, { colecciones: ['Cyber'] }];
    expect(coleccionesDelInventario(a)).toEqual(coleccionesDelInventario([...a].reverse()));
    expect(coleccionesDelInventario(a)).toEqual(['Cyber']);
  });

  it('ignora productos inactivos, valores vacíos y datos que no son listas', () => {
    const productos = [
      { activo: false, colecciones: ['Inactiva'] },
      { colecciones: ['', '   ', null, 3] },
      { colecciones: 'Cyber' },
      null,
    ];
    expect(coleccionesDelInventario(productos)).toEqual([]);
    expect(coleccionesDelInventario(undefined)).toEqual([]);
  });
});
