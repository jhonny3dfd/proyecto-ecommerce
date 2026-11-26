import { useEffect, useRef, useState } from 'react';
import clienteAxios from '../auth/axiosConfig';
import { MAX_DESTACADOS } from '../../hooks/useEdicionLanding';
import { CampoEditable } from './ControlesEdicion';
import SeccionDestacados from './SeccionDestacados';
import SeccionProductos from './SeccionProductos';

const clave = ({ tipo, id }) => `${tipo}:${id}`;

// Productos y publicaciones del panel, con la forma de la vitrina (GET catalogo/vitrina/) para la vista previa
const desdeProducto = (producto) => ({
  tipo: 'PRODUCTO', id: String(producto.id), nombre: producto.nombre, categoria: producto.categoria || '',
  imagen: producto.imagenes?.[0] || null,
  enlace: `/catalogo/producto/${producto.id}`, variantes: producto.variantes || [],
  publicado: producto.publicado !== false,
});
const desdePublicacion = (publicacion) => ({
  tipo: 'PUBLICACION', id: String(publicacion.id), nombre: publicacion.titulo, imagen: publicacion.portada || null,
  enlace: `/blog/${publicacion.slug}`, publicado: publicacion.estado === 'PUBLICADA',
});

// Por qué un elegido no se verá en la tienda (null si se ve). Lo mismo que filtra el backend (application/vitrina.py)
function motivoOculto(destacado, blogActivo) {
  if (!destacado.nombre) return 'Ya no existe: quítalo de la lista.';
  if (!destacado.publicado) {
    return destacado.tipo === 'PRODUCTO' ? 'Sin publicar: no se mostrará.' : 'En borrador: no se mostrará.';
  }
  if (destacado.tipo === 'PUBLICACION' && !blogActivo) return 'El blog está apagado: no se mostrará.';
  return null;
}

// Modo edición de la landing (RF-01.1, pedido de un cliente): el admin elige qué muestra la vitrina, "Más vendidos"
// (se llena sola) o "Destacados" (hasta 8 productos y publicaciones del blog que ordena con Subir y Bajar).
// La selección es un borrador de useEdicionLanding: se publica con "Guardar cambios", como el resto de la página.
export default function EditorVitrina({ edicion, vitrina, configuracion, nota }) {
  const modo = edicion.textos.vitrina_modo === 'DESTACADOS' ? 'DESTACADOS' : 'MAS_VENDIDOS';
  const blogActivo = Boolean(configuracion?.blog_activo);
  const [opciones, setOpciones] = useState(null);
  const [errorCarga, setErrorCarga] = useState('');
  const [elegido, setElegido] = useState('');
  const [anuncio, setAnuncio] = useState('');
  const botones = useRef({});
  const selector = useRef(null);

  // Los productos y las publicaciones se piden recién al elegir "Destacados"
  useEffect(() => {
    if (modo !== 'DESTACADOS' || opciones) return undefined;
    let vigente = true;
    Promise.all([clienteAxios.get('catalogo/productos/?todos=true'), clienteAxios.get('ventas/admin/blog/')])
      .then(([productos, publicaciones]) => {
        if (!vigente) return;
        setOpciones({
          productos: (Array.isArray(productos.data) ? productos.data : []).map(desdeProducto),
          publicaciones: (Array.isArray(publicaciones.data) ? publicaciones.data : []).map(desdePublicacion),
        });
      })
      .catch(() => {
        if (vigente) setErrorCarga('No se pudieron cargar tus productos y publicaciones. Sal del modo edición y vuelve a entrar.');
      });
    return () => { vigente = false; };
  }, [modo, opciones]);

  const porClave = new Map([...(opciones?.productos || []), ...(opciones?.publicaciones || [])]
    .map((opcion) => [clave(opcion), opcion]));
  const seleccion = (edicion.destacados || []).map((destacado) => {
    const datos = porClave.get(clave(destacado)) || { ...destacado, nombre: '', publicado: false };
    return { ...datos, motivo: opciones ? motivoOculto(datos, blogActivo) : null };
  });
  const vistaPrevia = opciones ? seleccion.filter((destacado) => !destacado.motivo) : [];
  const elegidos = new Set(seleccion.map(clave));
  const productosLibres = (opciones?.productos || []).filter((opcion) => opcion.publicado && !elegidos.has(clave(opcion)));
  const publicacionesLibres = (opciones?.publicaciones || [])
    .filter((opcion) => opcion.publicado && !elegidos.has(clave(opcion)));
  const completo = seleccion.length >= MAX_DESTACADOS;
  const nombreDe = (destacado) => destacado.nombre || 'Elemento eliminado';

  const agregar = () => {
    const opcion = porClave.get(elegido);
    if (!opcion || completo) return;
    edicion.agregarDestacado(opcion);
    setAnuncio(`${opcion.nombre} agregado a los destacados: ${seleccion.length + 1} de ${MAX_DESTACADOS}.`);
    setElegido('');
  };

  const mover = (indice, paso) => {
    const destacado = seleccion[indice];
    const destino = indice + paso;
    edicion.moverDestacado(indice, paso);
    setAnuncio(`${nombreDe(destacado)}: posición ${destino + 1} de ${seleccion.length}.`);
    // En un extremo el botón queda desactivado: el foco pasa al otro, para no perderlo
    const extremo = destino === 0 || destino === seleccion.length - 1;
    requestAnimationFrame(() => botones.current[`${clave(destacado)}:${extremo ? -paso : paso}`]?.focus());
  };

  const quitar = (indice) => {
    const destacado = seleccion[indice];
    edicion.quitarDestacado(indice);
    setAnuncio(`${nombreDe(destacado)} quitado de los destacados.`);
    requestAnimationFrame(() => selector.current?.focus());
  };

  const opcionesModo = [
    { valor: 'MAS_VENDIDOS', titulo: 'Más vendidos', detalle: 'Se llena sola con tus productos más vendidos.' },
    { valor: 'DESTACADOS', titulo: 'Destacados',
      detalle: `Tú eliges hasta ${MAX_DESTACADOS} productos o publicaciones del blog.` },
  ];

  return (
    <>
      <div className="contenedor editor-vitrina">
        <fieldset className="editor-vitrina-modo">
          <legend className="campo-editable-etiqueta">Qué muestra la vitrina de la página de inicio</legend>
          {opcionesModo.map(({ valor, titulo, detalle }) => (
            <label key={valor} className="editor-vitrina-opcion">
              <input type="radio" name="vitrina-modo" value={valor} checked={modo === valor}
                onChange={() => edicion.cambiarTexto('vitrina_modo', valor)} />
              <span><strong>{titulo}</strong> <span className="texto-secundario">{detalle}</span></span>
            </label>
          ))}
        </fieldset>
      </div>

      {modo === 'DESTACADOS' ? (
        <SeccionDestacados titulo={edicion.textos.destacados_titulo} destacados={vistaPrevia}
          nombreBlog={configuracion?.blog_nombre}
          editorTitulo={<CampoEditable campo="destacados_titulo" edicion={edicion} className="destacados-titulo-campo" />}>
          <div className="editor-destacados">
            <p role="status" aria-live="polite" className="visualmente-oculto">{anuncio}</p>
            {/* Sin role="alert": la barra de edición ya anuncia todos los errores al guardar */}
            {edicion.errores.destacados && <p className="editor-destacados-error">{edicion.errores.destacados}</p>}
            {errorCarga ? (
              <p role="alert" className="editor-destacados-error">{errorCarga}</p>
            ) : !opciones ? (
              <p className="texto-secundario">Cargando tus productos y publicaciones...</p>
            ) : (
              <>
                <h3 className="editor-destacados-titulo" id="destacados-elegidos">
                  Tus destacados ({seleccion.length} de {MAX_DESTACADOS})
                </h3>
                {seleccion.length > 0 ? (
                  <ol className="editor-destacados-lista lista-sin-estilo" aria-labelledby="destacados-elegidos">
                    {seleccion.map((destacado, indice) => (
                      <li key={clave(destacado)} className="editor-destacados-fila">
                        <span className="editor-destacados-miniatura" aria-hidden="true">
                          {destacado.imagen ? <img src={destacado.imagen} alt="" /> : nombreDe(destacado).charAt(0)}
                        </span>
                        <span className="editor-destacados-texto">
                          <strong>{nombreDe(destacado)}</strong>
                          <span className="texto-secundario">
                            {destacado.tipo === 'PRODUCTO' ? 'Producto' : 'Publicación del blog'}
                          </span>
                          {destacado.motivo && <span className="editor-destacados-aviso">{destacado.motivo}</span>}
                        </span>
                        <span className="editor-destacados-acciones">
                          {[[-1, 'Subir'], [1, 'Bajar']].map(([paso, texto]) => (
                            <button key={paso} type="button" className="boton-edicion"
                              ref={(boton) => { botones.current[`${clave(destacado)}:${paso}`] = boton; }}
                              aria-label={`${texto} ${nombreDe(destacado)}`}
                              disabled={paso === -1 ? indice === 0 : indice === seleccion.length - 1}
                              onClick={() => mover(indice, paso)}>
                              {texto}
                            </button>
                          ))}
                          <button type="button" className="boton-edicion" aria-label={`Quitar ${nombreDe(destacado)}`}
                            onClick={() => quitar(indice)}>
                            Quitar
                          </button>
                        </span>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="texto-secundario">Todavía no eliges ninguno.</p>
                )}

                <div className="editor-destacados-agregar">
                  <label htmlFor="destacados-opcion" className="campo-editable-etiqueta">
                    Agregar un producto o una publicación
                  </label>
                  <div className="editor-destacados-agregar-controles">
                    <select id="destacados-opcion" ref={selector} value={elegido} disabled={completo}
                      aria-describedby="destacados-agregar-ayuda" onChange={(e) => setElegido(e.target.value)}>
                      <option value="">Elige uno...</option>
                      {productosLibres.length > 0 && (
                        <optgroup label="Productos">
                          {productosLibres.map((opcion) => (
                            <option key={clave(opcion)} value={clave(opcion)}>{opcion.nombre}</option>
                          ))}
                        </optgroup>
                      )}
                      {publicacionesLibres.length > 0 && (
                        <optgroup label="Publicaciones del blog">
                          {publicacionesLibres.map((opcion) => (
                            <option key={clave(opcion)} value={clave(opcion)}>{opcion.nombre}</option>
                          ))}
                        </optgroup>
                      )}
                    </select>
                    <button type="button" className="boton-edicion" disabled={completo || !elegido} onClick={agregar}>
                      Agregar
                    </button>
                  </div>
                  <p id="destacados-agregar-ayuda" className="texto-secundario editor-destacados-ayuda">
                    {completo
                      ? `Ya elegiste ${MAX_DESTACADOS}: quita uno para agregar otro.`
                      : 'Solo aparecen los productos y las publicaciones que ya están publicados.'}
                    {!blogActivo && ' Las publicaciones del blog no se mostrarán mientras el blog esté apagado.'}
                  </p>
                </div>

                {vistaPrevia.length === 0 && (
                  <p className="seccion-landing-nota editor-destacados-nota">
                    Mientras no haya destacados visibles, la página muestra «Más vendidos».
                  </p>
                )}
              </>
            )}
          </div>
        </SeccionDestacados>
      ) : vitrina?.mas_vendidos?.length || !vitrina ? (
        <SeccionProductos id="mas-vendidos" antetitulo="Lo más elegido" titulo="Más vendidos"
          productos={vitrina?.mas_vendidos} cargando={!vitrina} alterna nota={nota} />
      ) : (
        <section className="seccion-landing seccion-landing--alterna" aria-labelledby="mas-vendidos-titulo">
          <div className="contenedor">
            <h2 id="mas-vendidos-titulo">Más vendidos</h2>
            <p className="seccion-landing-nota">Al guardar, aquí se verán tus productos más vendidos.</p>
          </div>
        </section>
      )}
    </>
  );
}
