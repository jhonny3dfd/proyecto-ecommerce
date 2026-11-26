// Imita al traductor del navegador (Chrome usa el de Google): cambia cada texto de la página por
// <font><font>texto traducido</font></font>, como se vio en una tienda publicada, y traduce también lo que aparece
// después. Respeta translate="no" y .notranslate, igual que Google. La traducción falsa antepone "EN·": así un texto
// que React no pudo actualizar (el viejo, traducido) se distingue del nuevo. No llama a ningún servicio externo.
export const MARCA = 'EN·';

export async function traducirComoElNavegador(page) {
  await page.evaluate((marca) => {
    const SALTAR = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEXTAREA', 'OPTION', 'TITLE']);
    const traducir = (nodo) => {
      const padre = nodo.parentElement;
      if (!padre || SALTAR.has(padre.tagName) || !nodo.nodeValue.trim()) return;
      if (padre.closest('[translate="no"], .notranslate, font[data-traducido]')) return;
      const externo = document.createElement('font');
      externo.dataset.traducido = '';
      externo.style.verticalAlign = 'inherit';
      const interno = document.createElement('font');
      interno.style.verticalAlign = 'inherit';
      interno.textContent = marca + nodo.nodeValue;
      externo.appendChild(interno);
      padre.replaceChild(externo, nodo);
    };
    const recorrer = (raiz) => {
      const caminante = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
      const nodos = [];
      while (caminante.nextNode()) nodos.push(caminante.currentNode);
      nodos.forEach(traducir);
    };
    recorrer(document.body);
    new MutationObserver((cambios) => {
      for (const cambio of cambios) {
        if (cambio.type === 'characterData') traducir(cambio.target);
        cambio.addedNodes.forEach((nodo) => {
          if (nodo.nodeType === Node.TEXT_NODE) traducir(nodo);
          else if (nodo.nodeType === Node.ELEMENT_NODE) recorrer(nodo);
        });
      }
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
    document.documentElement.classList.add('translated-ltr');
  }, MARCA);
}
