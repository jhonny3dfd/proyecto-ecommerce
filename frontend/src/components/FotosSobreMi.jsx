// Hasta 2 fotos para la página Sobre mí (pedido de un cliente, opcionales), cada una con su texto alternativo.
// `fotos`: { 1: { url, archivo, vista, alt }, 2: {...} }; archivo es el File elegido, sin subir todavía, y url la
// foto guardada (null si no hay o se quitó). Se guardan con el botón "Guardar Sobre mí"
const FORMATOS_FOTO = ['image/jpeg', 'image/png', 'image/webp'];
const LARGO_ALT = 150;

export default function FotosSobreMi({ fotos, onCambiar, errores = {} }) {
  const elegir = (numero, e) => {
    const [archivo] = e.target.files;
    e.target.value = '';
    if (!archivo) return;
    if (!FORMATOS_FOTO.includes(archivo.type)) {
      onCambiar(numero, {}, 'Solo se permiten imágenes JPG, PNG o WebP.');
      return;
    }
    onCambiar(numero, { archivo, vista: URL.createObjectURL(archivo) });
  };

  return (
    <fieldset className="admin-opciones sobre-mi-fotos-panel">
      <legend>Fotos (opcional)</legend>
      <p className="admin-ayuda">
        Hasta 2 fotos que se muestran junto a tu biografía, por ejemplo tú en tu taller o uno de tus trabajos.
        Describe cada una: lo leen las personas que usan lector de pantalla.
      </p>
      <div className="sobre-mi-fotos-panel-lista">
        {[1, 2].map((numero) => {
          const foto = fotos[numero];
          const imagen = foto.vista || foto.url;
          const campo = `sobre_mi_foto_${numero}`;
          const error = errores[campo] || errores[`${campo}_alt`];
          return (
            <div key={numero} className="admin-campo sobre-mi-foto-panel">
              <span className="publicacion-etiqueta" id={`${campo}-etiqueta`}>Foto {numero}</span>
              {imagen ? (
                <img className="sobre-mi-foto-vista" src={imagen} alt={`Vista previa de la foto ${numero}`} />
              ) : (
                <p className="admin-ayuda">Sin foto.</p>
              )}
              <div className="publicacion-acciones">
                <input id={campo} type="file" accept={FORMATOS_FOTO.join(',')} onChange={(e) => elegir(numero, e)}
                  className="visualmente-oculto galeria-input" aria-labelledby={`${campo}-etiqueta ${campo}-boton`}
                  aria-describedby={error ? `${campo}-error` : undefined} />
                <label id={`${campo}-boton`} htmlFor={campo} className="boton boton-contorno galeria-zona">
                  {imagen ? 'Cambiar foto' : 'Elegir foto'}
                </label>
                {imagen && (
                  <button type="button" className="boton boton-contorno" aria-label={`Quitar la foto ${numero}`}
                    onClick={() => onCambiar(numero, { archivo: null, vista: null, url: null, alt: '' })}>
                    Quitar
                  </button>
                )}
              </div>
              {imagen && (
                <>
                  <label htmlFor={`${campo}-alt`}>Descripción de la foto {numero}</label>
                  <input id={`${campo}-alt`} type="text" maxLength={LARGO_ALT} value={foto.alt}
                    placeholder="Ej. Pintando un mural en el taller"
                    onChange={(e) => onCambiar(numero, { alt: e.target.value })} />
                </>
              )}
              {error && <p id={`${campo}-error`} className="admin-error-campo">{error}</p>}
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}
