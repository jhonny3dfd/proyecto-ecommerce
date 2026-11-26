import { useId, useRef, useState } from 'react';
import { CampoEditable } from './ControlesEdicion';
import { TEXTOS_FOTO } from '../../hooks/useEdicionLanding';
import { botonDeFoto, resolverMenu } from '../../utils/menuPrincipal';

// Páginas del header a las que puede llevar el botón de una foto (domain/banner.py)
const DESTINOS = [
  { valor: 'INICIO', enlace: 'inicio', etiqueta: 'Inicio' },
  { valor: 'CATALOGO', enlace: 'catalogo', etiqueta: 'Catálogo' },
  { valor: 'BLOG', enlace: 'nosotros', etiqueta: 'Blog', modulo: 'blog_activo' },
  { valor: 'COTIZAR', enlace: 'cotizar', etiqueta: 'Cotizar', modulo: 'cotizaciones_activas' },
];

// SCRUM-194: en el modo edición de la landing, el admin pasa de una foto del carrusel a otra y edita los textos
// y el botón de la que está viendo. Blog y Cotizar solo se ofrecen con su módulo activo
export default function EditorTextosFoto({ configuracion, edicion }) {
  const id = useId();
  const [anuncio, setAnuncio] = useState('');
  const botones = useRef({});
  const fotos = edicion.banners;
  const total = fotos.length;
  const indice = edicion.fotoEditada;
  const foto = fotos[indice];
  const nombres = Object.fromEntries(resolverMenu(configuracion).map((enlace) => [enlace.id, enlace.nombre]));
  const opciones = DESTINOS.filter(({ valor, modulo }) => !modulo || configuracion?.[modulo] || valor === foto.destino);
  const boton = botonDeFoto(configuracion, foto.destino);

  // Los campos editan la foto que se ve; el error del título viene del guardado
  const campos = {
    textos: foto,
    errores: { titulo: edicion.errores.banner_titulo },
    cambiarTexto: edicion.cambiarTextoFoto,
  };

  const ir = (paso) => {
    const destino = indice + paso;
    edicion.seleccionarFoto(destino);
    setAnuncio(`Foto ${destino + 1} de ${total}.`);
    // En un extremo el botón queda desactivado: el foco pasa al otro para no perderse
    const siguienteFoco = destino === 0 ? 1 : destino === total - 1 ? -1 : paso;
    requestAnimationFrame(() => botones.current[siguienteFoco]?.focus());
  };

  return (
    <>
      {total > 1 && (
        <div className="portada-editor-navegacion">
          {[-1, 1].map((paso) => (
            <button key={paso} type="button" className="boton-edicion"
              ref={(elemento) => { botones.current[paso] = elemento; }}
              disabled={paso === -1 ? indice === 0 : indice === total - 1}
              onClick={() => ir(paso)}>
              {paso === -1 ? '← Foto anterior' : 'Foto siguiente →'}
            </button>
          ))}
          <span className="portada-editor-posicion">Foto {indice + 1} de {total}</span>
          <span role="status" className="visualmente-oculto">{anuncio}</span>
        </div>
      )}

      <CampoEditable campo="antetitulo" definicion={TEXTOS_FOTO.antetitulo} edicion={campos} claro
        ancho="campo-ancho-medio" className="antetitulo portada-antetitulo" />
      <h1 id="portada-titulo" className="visualmente-oculto">{foto.titulo}</h1>
      <CampoEditable campo="titulo" definicion={TEXTOS_FOTO.titulo} edicion={campos} claro multilinea
        ancho="campo-ancho-titulo" className="portada-titulo portada-titulo--campo" />
      <CampoEditable campo="texto" definicion={TEXTOS_FOTO.texto} edicion={campos} claro multilinea filas={3}
        ancho="campo-ancho-medio" className="portada-texto" />

      <div className="campo-editable campo-editable--claro portada-editor-destino">
        <label htmlFor={`${id}-destino`} className="campo-editable-etiqueta">El botón lleva a</label>
        <select id={`${id}-destino`} className="campo-editable-control" value={foto.destino}
          aria-describedby={`${id}-destino-ayuda`}
          onChange={(e) => edicion.cambiarTextoFoto('destino', e.target.value)}>
          {opciones.map(({ valor, enlace, etiqueta, modulo }) => (
            <option key={valor} value={valor}>
              {/* Con el módulo activo, el nombre que tiene en el menú */}
              {modulo && !configuracion?.[modulo] ? `${etiqueta} (apagado: no se muestra)` : nombres[enlace] ?? etiqueta}
            </option>
          ))}
        </select>
        <span id={`${id}-destino-ayuda`} className="campo-editable-ayuda">
          {boton ? `El botón dirá "${boton.texto}".` : 'Con ese módulo apagado, esta foto no muestra botón.'}
        </span>
      </div>

      {boton && <span className="boton boton-primario portada-boton">{boton.texto}</span>}
      {edicion.errores.banner_orden && (
        <p role="alert" className="campo-editable-ayuda campo-editable-ayuda--error">{edicion.errores.banner_orden}</p>
      )}
    </>
  );
}
