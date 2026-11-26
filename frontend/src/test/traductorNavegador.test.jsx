import { afterEach, describe, expect, it } from 'vitest';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { protegerDelTraductor } from '../utils/traductorNavegador';

// El traductor del navegador cambia cada texto por <font><font>traducción</font></font>
function traducir(raiz) {
  const caminante = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
  const textos = [];
  while (caminante.nextNode()) textos.push(caminante.currentNode);
  for (const texto of textos) {
    const externo = document.createElement('font');
    const interno = document.createElement('font');
    interno.textContent = `EN·${texto.nodeValue}`;
    externo.appendChild(interno);
    texto.parentNode.replaceChild(externo, texto);
  }
}

// Un botón como los de la tienda: el spinner se inserta delante del texto mientras espera
function Boton({ cargando }) {
  return <button type="button">{cargando && <b>…</b>}{cargando ? 'Verificando' : 'Agregar al carrito'}</button>;
}

function montar() {
  const contenedor = document.createElement('div');
  document.body.appendChild(contenedor);
  const raiz = createRoot(contenedor);
  act(() => raiz.render(<Boton cargando={false} />));
  traducir(contenedor);
  return { contenedor, raiz };
}

describe('protegerDelTraductor', () => {
  const originales = { removeChild: Node.prototype.removeChild, insertBefore: Node.prototype.insertBefore };

  afterEach(() => {
    Object.assign(Node.prototype, originales);
    document.body.innerHTML = '';
  });

  it('sin la protección, React se cae al insertar junto a un texto traducido', () => {
    const { raiz } = montar();
    expect(() => act(() => raiz.render(<Boton cargando />))).toThrow();
  });

  it('con la protección, la página sigue funcionando al ir y volver', () => {
    protegerDelTraductor();
    const { contenedor, raiz } = montar();

    act(() => raiz.render(<Boton cargando />));
    expect(contenedor.querySelector('b')).not.toBeNull();
    act(() => raiz.render(<Boton cargando={false} />));

    expect(contenedor.querySelector('b')).toBeNull();
    expect(contenedor.querySelector('button')).not.toBeNull();
  });

  it('se aplica una sola vez', () => {
    protegerDelTraductor();
    const quitar = Node.prototype.removeChild;
    protegerDelTraductor();
    expect(Node.prototype.removeChild).toBe(quitar);
  });
});
