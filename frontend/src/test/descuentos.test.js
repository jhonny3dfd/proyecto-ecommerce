import { describe, expect, it } from 'vitest';
import { elegirDescuento, montoDescuento, siguienteAutomatico } from '../utils/descuentos';

// El mismo comportamiento que domain/promociones.py (ElegirPromocionTests)
describe('descuentos', () => {
  const porcentaje = { tipo_descuento: 'PORCENTAJE', valor_descuento: 10, monto_minimo: null, umbral_envio_gratis: null };
  const conEnvio = { tipo_descuento: 'MONTO_FIJO', valor_descuento: 1000, monto_minimo: null, umbral_envio_gratis: 15000 };

  it('respeta el monto mínimo y nunca descuenta más que el subtotal', () => {
    const conMinimo = { ...porcentaje, monto_minimo: 30000 };
    expect(montoDescuento(conMinimo, 29999)).toBe(0);
    expect(montoDescuento(conMinimo, 30000)).toBe(3000);
    expect(montoDescuento({ ...conEnvio, valor_descuento: 9000 }, 5000)).toBe(5000);
  });

  it('elige el que más ahorra contando el envío gratis', () => {
    expect(elegirDescuento([porcentaje, conEnvio], 20000, 3990)).toBe(conEnvio);
    expect(elegirDescuento([porcentaje, conEnvio], 20000, 0)).toBe(porcentaje);
    expect(elegirDescuento([], 20000, 0)).toBeNull();
  });

  it('el siguiente automático es el más cercano que no se alcanza', () => {
    const a = { ...porcentaje, monto_minimo: 50000 };
    const b = { ...porcentaje, monto_minimo: 30000 };
    expect(siguienteAutomatico([a, b], 20000)).toBe(b);
    expect(siguienteAutomatico([a, b], 60000)).toBeNull();
  });
});
