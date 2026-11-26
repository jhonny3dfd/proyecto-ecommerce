import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { botonDeFoto, textoBotonCatalogo } from '../../utils/menuPrincipal';
import { PORTADA_POR_DEFECTO, TEXTOS_POR_DEFECTO } from './textosPorDefecto';
import { CampoEditable, EditorFotosBanner } from './ControlesEdicion';
import EditorTextosFoto from './EditorTextosFoto';

// RF-01.1, SCRUM-194: portada de la landing con banner en carrusel de fundido suave y campos fijos que
// edita el admin (antetítulo, título, texto, botón y fotos del carrusel).
// Con 2+ fotos cambian solas con fundido y botón de pausa (WCAG 2.2.2). Con 1 foto queda fija.
// El botón toma el nombre del catálogo (Ver <nombre del catálogo>); la foto prioriza la subida sobre banner_url.
// Las fotos no son clickeables y el velo garantiza contraste AA sobre todas las fotos.

// Íconos de los controles en SVG: los caracteres ▶ y ⏸ se ven como emoji en iPhone y Android, y ‹ › cambian con la
// tipografía de la tienda. Así se ven iguales en todos los dispositivos (pedido de Alan, 2026-11-13)
const ICONOS_CARRUSEL = {
  anterior: <path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
    strokeLinejoin="round" />,
  siguiente: <path d="M9 5l7 7-7 7" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
    strokeLinejoin="round" />,
  pausar: <path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" fill="currentColor" />,
  reanudar: <path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z"
    fill="currentColor" />,
};

function IconoCarrusel({ nombre }) {
  return (
    <svg className="portada-icono-carrusel" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"
      focusable="false">
      {ICONOS_CARRUSEL[nombre]}
    </svg>
  );
}

export default function Portada({ configuracion, edicion }) {
  const listaFotos = (configuracion.banners && configuracion.banners.length > 0)
    ? configuracion.banners
    : (configuracion.banner || configuracion.banner_url?.trim()
        ? [{ id: 'default', imagen: configuracion.banner || configuracion.banner_url.trim() }]
        : [{ id: 'default', imagen: PORTADA_POR_DEFECTO }]);

  const editando = Boolean(edicion?.editando);
  const [indiceActivo, setIndiceActivo] = useState(0);
  const [pausado, setPausado] = useState(false);
  const videosRef = useRef({});
  const [movimientoReducido, setMovimientoReducido] = useState(() =>
    typeof window !== 'undefined' && Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches));
  const [ahorroDatos] = useState(() => typeof navigator !== 'undefined' && Boolean(navigator.connection?.saveData));
  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!media) return undefined;
    const actualizar = () => setMovimientoReducido(media.matches);
    media.addEventListener?.('change', actualizar);
    return () => media.removeEventListener?.('change', actualizar);
  }, []);
  // WCAG 2.2.2: mientras el mouse o el foco están sobre los textos o el botón, la foto no cambia
  const [enUso, setEnUso] = useState(false);
  // Al cambiar de foto con las flechas, el reloj vuelve a empezar y se anuncia la posición
  const [reinicio, setReinicio] = useState(0);
  const [anuncio, setAnuncio] = useState('');
  const salirDe = (e) => { if (!e.currentTarget.contains(e.relatedTarget)) setEnUso(false); };

  const totalFotos = listaFotos.length;
  // En el modo edición se ve la foto que el admin está editando
  const editandoFotos = editando && edicion.banners?.length > 0;
  const indiceSeguro = editandoFotos ? edicion.fotoEditada : totalFotos > 0 ? indiceActivo % totalFotos : 0;
  const permitirVideo = Boolean(configuracion.video_banner_activo) && !ahorroDatos && !movimientoReducido && !editando;
  // Si el video no se puede reproducir, el carrusel vuelve a cambiar cada 5 segundos para no quedarse pegado
  const [videoConError, setVideoConError] = useState(false);
  // Con el video en pantalla, el carrusel espera a que termine en vez de cambiar a los 5 segundos
  const esperaVideo = permitirVideo && Boolean(listaFotos[indiceSeguro]?.video) && !videoConError;
  // El video de la diapositiva activa solo se detiene con el botón de pausa (WCAG 2.2.2). El mouse o el foco sobre
  // los textos o las flechas (enUso) frenan el cambio de diapositiva, no el video: si no, al llegar con una flecha el
  // foco queda en ella y el video no partía hasta hacer clic en otro lado
  useEffect(() => {
    Object.entries(videosRef.current).forEach(([indice, video]) => {
      if (!video) return;
      if (permitirVideo && Number(indice) === indiceSeguro && !pausado) {
        const resultado = video.play();
        resultado?.catch?.(() => {});
      } else video.pause();
    });
  }, [indiceSeguro, pausado, permitirVideo, totalFotos]);
  const imagenActual = listaFotos[indiceSeguro]?.imagen || PORTADA_POR_DEFECTO;

  // Textos y botón de la foto que se ve; sin fotos propias, los generales de la portada con el botón al catálogo
  const fotoActual = listaFotos[indiceSeguro];
  const textos = fotoActual?.titulo ? fotoActual : {
    antetitulo: configuracion.subtitulo_bienvenida, titulo: configuracion.texto_bienvenida,
    texto: configuracion.texto_landing, destino: 'CATALOGO',
  };
  const boton = botonDeFoto(configuracion, textos.destino);

  // Rendimiento (Point 12): Carga solo la diapositiva activa y precarga la siguiente, evitando descargar todas de golpe
  const [fotosCargadas, setFotosCargadas] = useState(() => new Set([0, 1]));

  // Pasa a la diapositiva siguiente y deja cargadas esa y la que viene después
  const avanzar = useCallback(() => {
    setIndiceActivo((actual) => {
      const siguiente = (actual + 1) % totalFotos;
      const subsiguiente = (siguiente + 1) % totalFotos;
      setFotosCargadas((cargadas) => {
        if (cargadas.has(siguiente) && cargadas.has(subsiguiente)) return cargadas;
        const nuevo = new Set(cargadas);
        nuevo.add(siguiente);
        nuevo.add(subsiguiente);
        return nuevo;
      });
      return siguiente;
    });
  }, [totalFotos]);

  useEffect(() => {
    if (totalFotos <= 1 || pausado || enUso || editando || esperaVideo) return undefined;
    const intervalo = setInterval(avanzar, 5000);
    return () => clearInterval(intervalo);
  }, [totalFotos, pausado, enUso, editando, reinicio, esperaVideo, avanzar]);

  // Al terminar el video se pasa a la siguiente diapositiva. Si en ese momento el mouse o el foco están sobre los
  // textos o las flechas (WCAG 2.2.2), el video vuelve a empezar y la diapositiva no cambia
  const alTerminarVideo = (evento) => {
    if (enUso) {
      evento.currentTarget.play()?.catch?.(() => {});
      return;
    }
    avanzar();
  };

  // Flechas del carrusel: circulares, cargan la foto elegida y sus vecinas
  const irA = (paso) => {
    const destino = (indiceSeguro + paso + totalFotos) % totalFotos;
    setIndiceActivo(destino);
    setFotosCargadas((cargadas) => new Set([...cargadas, destino, (destino + 1) % totalFotos,
      (destino - 1 + totalFotos) % totalFotos]));
    setReinicio((actual) => actual + 1);
    setAnuncio(`Foto ${destino + 1} de ${totalFotos}.`);
  };

  const textoBoton = textoBotonCatalogo(configuracion);


  return (
    <section className={`portada${editando ? ' portada--editando' : ''}${esperaVideo ? ' portada--con-video' : ''}`}
      aria-labelledby="portada-titulo"
      style={{ backgroundImage: `url("${imagenActual}")` }}>
      {/* Carrusel de diapositivas con fundido suave (no clickeables) */}
      <div className="portada-carrusel" aria-hidden="true">
        {listaFotos.map((foto, index) => {
          const debeCargar = fotosCargadas.has(index) || editando;
          const cargarVideo = permitirVideo && Boolean(foto.video) &&
            (index === indiceSeguro || index === (indiceSeguro + 1) % totalFotos);
          return (
            <div
              key={foto.id ?? index}
              className={`portada-diapositiva ${index === indiceSeguro ? 'portada-diapositiva--activa' : ''}`}
              style={debeCargar ? { backgroundImage: `url("${foto.imagen}")` } : undefined}
            >
              {/* En bucle solo si es la única diapositiva; con más, al terminar pasa a la siguiente */}
              {cargarVideo && <video ref={(elemento) => { videosRef.current[index] = elemento; }}
                src={foto.video} poster={foto.imagen} loop={totalFotos <= 1}
                onEnded={totalFotos > 1 ? alTerminarVideo : undefined} onError={() => setVideoConError(true)}
                muted playsInline preload="metadata" aria-hidden="true" />}
            </div>
          );
        })}
      </div>

      <div className="portada-velo" aria-hidden="true" />

      {editando && (
        <div className="contenedor portada-controles">
          <EditorFotosBanner banners={edicion?.banners || listaFotos} edicion={edicion} claro />
        </div>
      )}

      {/* Con 2+ fotos: flechas y pausa juntas, abajo a la derecha para no tapar los textos (WCAG 2.2.2).
          Mientras el foco está en ellas, la foto no cambia sola */}
      {(totalFotos >= 2 || (permitirVideo && Boolean(fotoActual?.video))) && !editando && (
        <div className="portada-controles-carrusel" role="group" aria-label="Controles del carrusel"
          onFocus={() => setEnUso(true)} onBlur={salirDe}>
          {/* Con el video como única diapositiva solo queda la pausa (WCAG 2.2.2) */}
          {totalFotos >= 2 && (
            <button type="button" className="portada-control-carrusel" aria-label="Foto anterior" onClick={() => irA(-1)}>
              <IconoCarrusel nombre="anterior" />
            </button>
          )}
          {/* Solo el ícono (pedido de Alan): el nombre lo anuncia el lector de pantalla y lo muestra el tooltip */}
          <button
            type="button"
            className="portada-control-carrusel"
            onClick={() => setPausado((p) => !p)}
            aria-label={pausado ? 'Reanudar carrusel' : 'Pausar carrusel'}
            title={pausado ? 'Reanudar carrusel' : 'Pausar carrusel'}
          >
            <IconoCarrusel nombre={pausado ? 'reanudar' : 'pausar'} />
          </button>
          {totalFotos >= 2 && (
            <button type="button" className="portada-control-carrusel" aria-label="Foto siguiente" onClick={() => irA(1)}>
              <IconoCarrusel nombre="siguiente" />
            </button>
          )}
          <span className="portada-posicion-carrusel" aria-hidden="true">{indiceSeguro + 1} / {totalFotos}</span>
          <span role="status" className="visualmente-oculto">{anuncio}</span>
        </div>
      )}

      <div className="contenedor portada-contenido"
        onMouseEnter={() => setEnUso(true)} onMouseLeave={() => setEnUso(false)}
        onFocus={() => setEnUso(true)} onBlur={salirDe}>
        {editandoFotos ? (
          <EditorTextosFoto configuracion={configuracion} edicion={edicion} />
        ) : editando ? (
          <>
            <CampoEditable campo="subtitulo_bienvenida" edicion={edicion} claro ancho="campo-ancho-medio"
              className="antetitulo portada-antetitulo" />
            <h1 id="portada-titulo" className="visualmente-oculto">{configuracion.texto_bienvenida}</h1>
            <CampoEditable campo="texto_bienvenida" edicion={edicion} claro multilinea ancho="campo-ancho-titulo"
              className="portada-titulo portada-titulo--campo" />
            <CampoEditable campo="texto_landing" edicion={edicion} claro multilinea filas={3}
              ancho="campo-ancho-medio" className="portada-texto" />
            <span className="boton boton-primario portada-boton">{textoBoton}</span>
          </>
        ) : (
          <>
            {textos.antetitulo && (
              <span className="antetitulo portada-antetitulo">{textos.antetitulo}</span>
            )}
            <h1 id="portada-titulo" className="portada-titulo">
              {textos.titulo || TEXTOS_POR_DEFECTO.texto_bienvenida}
            </h1>
            {textos.texto && <p className="portada-texto">{textos.texto}</p>}
            {boton && (
              <Link to={boton.to} className="boton boton-primario portada-boton">
                {boton.texto}
                <span aria-hidden="true">→</span>
              </Link>
            )}
          </>
        )}
      </div>
    </section>
  );
}
