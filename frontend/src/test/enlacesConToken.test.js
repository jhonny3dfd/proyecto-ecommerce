import { afterEach, describe, expect, it } from 'vitest';
import {
  capturarTokensDeEnlace, guardarTokensDeEnlace, leerTokensDeEnlace, olvidarTokensDeEnlace,
} from '../utils/enlacesConToken';

describe('Tokens de los enlaces de los correos', () => {
  afterEach(() => {
    olvidarTokensDeEnlace('/restablecer-contrasena');
    olvidarTokensDeEnlace('/resena');
    window.history.replaceState(null, '', '/');
  });

  it('el de nueva contraseña se guarda y sale de la URL antes de montar la app, para que la analítica no lo reciba', () => {
    window.history.replaceState({ previo: 1 }, '', '/restablecer-contrasena?uid=MQ&token=abc-123');
    capturarTokensDeEnlace();

    expect(window.location.pathname + window.location.search).toBe('/restablecer-contrasena');
    expect(window.history.state).toEqual({ previo: 1 });
    expect(leerTokensDeEnlace('/restablecer-contrasena')).toEqual({ uid: 'MQ', token: 'abc-123' });
  });

  it('el de la reseña también', () => {
    window.history.replaceState(null, '', `/resena?t=${encodeURIComponent('12:abc/def')}`);
    capturarTokensDeEnlace();

    expect(window.location.pathname + window.location.search).toBe('/resena');
    expect(leerTokensDeEnlace('/resena')).toEqual({ t: '12:abc/def' });
  });

  it('no toca otras páginas ni una URL a la que le falta parte del token', () => {
    window.history.replaceState(null, '', '/catalogo?t=abc');
    capturarTokensDeEnlace();
    expect(window.location.search).toBe('?t=abc');

    window.history.replaceState(null, '', '/restablecer-contrasena?uid=MQ');
    capturarTokensDeEnlace();
    expect(window.location.search).toBe('?uid=MQ');

    expect(leerTokensDeEnlace('/resena')).toBeNull();
    expect(leerTokensDeEnlace('/restablecer-contrasena')).toBeNull();
  });

  it('sobrevive a recargar la página y se olvida al usarlo', () => {
    guardarTokensDeEnlace('/resena', { t: 'firmado' });
    expect(JSON.parse(sessionStorage.getItem('enlace_con_token:/resena'))).toEqual({ t: 'firmado' });

    olvidarTokensDeEnlace('/resena');
    expect(leerTokensDeEnlace('/resena')).toBeNull();
    expect(sessionStorage.getItem('enlace_con_token:/resena')).toBeNull();
  });
});
