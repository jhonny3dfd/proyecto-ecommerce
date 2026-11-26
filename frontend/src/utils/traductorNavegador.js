// El traductor del navegador (Chrome usa el de Google) cambia los textos de la página por los suyos, dentro de
// <font>. Cuando React después quita o inserta algo junto a un texto que ya no está donde lo dejó, el navegador lanza
// un error y la página queda en blanco (probado en una tienda publicada: "Agregar al carrito" la dejaba vacía). Con
// esto, esas dos operaciones toleran que el traductor haya movido el nodo: la página sigue funcionando. Los textos que
// cambian conviene que vayan solos en su elemento (`<span>{texto}</span>`), así React los reemplaza enteros.
export function protegerDelTraductor(Nodo = typeof Node === 'function' ? Node : null) {
  if (!Nodo?.prototype || Nodo.prototype.removeChild.__protegido) return;

  const quitarOriginal = Nodo.prototype.removeChild;
  const quitar = function (hijo) {
    if (hijo.parentNode !== this) {
      // El traductor ya lo sacó o lo envolvió en su <font>: se quita de donde esté
      if (hijo.parentNode) quitarOriginal.call(hijo.parentNode, hijo);
      return hijo;
    }
    return quitarOriginal.call(this, hijo);
  };
  quitar.__protegido = true;
  Nodo.prototype.removeChild = quitar;

  const insertarOriginal = Nodo.prototype.insertBefore;
  Nodo.prototype.insertBefore = function (nuevo, referencia) {
    // La referencia ya no está aquí (el traductor la reemplazó): se agrega al final en vez de fallar
    if (referencia && referencia.parentNode !== this) return this.appendChild(nuevo);
    return insertarOriginal.call(this, nuevo, referencia);
  };
}
