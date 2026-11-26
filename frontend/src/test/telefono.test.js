import { describe, expect, it } from 'vitest';
import { soloCaracteresDeTelefono } from '../utils/telefono';

describe('soloCaracteresDeTelefono', () => {
  it('deja números, +, espacios, guiones y paréntesis, y quita letras y otros símbolos', () => {
    expect(soloCaracteresDeTelefono('+56 9 (1234)-5678')).toBe('+56 9 (1234)-5678');
    expect(soloCaracteresDeTelefono('llámame al 9 1234 abc 5678!')).toBe('  9 1234  5678');
    expect(soloCaracteresDeTelefono('')).toBe('');
  });
});
