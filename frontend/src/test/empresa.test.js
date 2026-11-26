import { describe, expect, it } from 'vitest';
import { EMPRESA_VACIA, normalizarRut, validarDatosEmpresa } from '../utils/empresa';

const EMPRESA = {
  razon_social: 'Comercial Andes SpA', rut: '76.123.456-0', giro: 'Venta de artículos de regalo',
  direccion: 'Av. Providencia 1234', correo: 'facturas@andes.test'
};

describe('RUT de la empresa (mismo cálculo que domain/empresa.py)', () => {
  it('acepta el RUT con o sin puntos y guion y lo deja con puntos', () => {
    for (const texto of ['76.123.456-0', '76123456-0', '761234560', ' 76.123.456 - 0 ']) {
      expect(normalizarRut(texto)).toBe('76.123.456-0');
    }
  });

  it('valida un RUT público conocido, el dígito K y uno de siete dígitos', () => {
    expect(normalizarRut('60803000-k')).toBe('60.803.000-K');
    expect(normalizarRut('5.126.663-3')).toBe('5.126.663-3');
  });

  it('rechaza un dígito verificador incorrecto o algo que no es un RUT', () => {
    for (const texto of ['76.123.456-1', '76.123.456', '1-9', '123.456.789-0', 'abc', '', null]) {
      expect(normalizarRut(texto)).toBeNull();
    }
  });
});

describe('validarDatosEmpresa', () => {
  it('sin errores cuando están todos los datos', () => {
    expect(validarDatosEmpresa(EMPRESA)).toEqual({});
  });

  it('marca cada dato que falta, el RUT inválido y el correo mal escrito', () => {
    expect(Object.keys(validarDatosEmpresa(EMPRESA_VACIA))).toEqual(['razon_social', 'rut', 'giro', 'direccion', 'correo']);
    expect(validarDatosEmpresa({ ...EMPRESA, rut: '76.123.456-1' }).rut).toMatch(/dígito verificador/);
    expect(validarDatosEmpresa({ ...EMPRESA, correo: 'facturas@' }).correo).toBe('Escribe un correo válido.');
  });
});
