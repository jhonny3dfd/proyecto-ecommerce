import { useEffect, useRef, useState } from 'react';
import clienteAxios from '../components/auth/axiosConfig';
import { recargarConfiguracion } from './useConfiguracionTienda';
import { MAX_DIAPOSITIVAS_BANNER } from '../constants/banner';

// Lo que el admin edita en la landing (RF-01.1, RF-01.2). Los máximos son los del backend.
export const CAMPOS_TEXTO = {
  nombre_tienda: { etiqueta: 'Nombre de la tienda', maximo: 255, obligatorio: true },
  subtitulo_bienvenida: { etiqueta: 'Antetítulo', maximo: 200 },
  texto_bienvenida: { etiqueta: 'Título', maximo: 300, obligatorio: true },
  texto_landing: { etiqueta: 'Texto de la portada', maximo: 1000 },
  nosotros_titulo: { etiqueta: 'Título de Nosotros', maximo: 120 },
  nosotros_texto: { etiqueta: 'Texto de Nosotros', maximo: 2000 },
  // RN-01: dónde va el logo de la Universidad: 'HEADER' (o vacío) o 'FOOTER'; no hay opción para ocultarlo
  ubicacion_logo_universidad: { etiqueta: 'Logo de la Universidad' },
  // Vitrina: 'MAS_VENDIDOS' (o vacío) o 'DESTACADOS'; vacío el título vuelve a "Destacados" (domain/destacados.py)
  vitrina_modo: { etiqueta: 'Vitrina' },
  destacados_titulo: { etiqueta: 'Título de la sección', maximo: 60 }
};

// Destacados: hasta 8 productos y publicaciones del blog, en el orden que elige el admin (domain/destacados.py)
export const MAX_DESTACADOS = 8;

// Fotos de la sección de Instagram: 6 espacios fijos (el usuario se configura en el panel)
export const CAMPOS_FOTOS_INSTAGRAM = [1, 2, 3, 4, 5, 6].map((numero) => `instagram_foto_${numero}`);

export const CAMPOS_IMAGEN = {
  logo: 'logo',
  favicon: 'favicon',
  banner: 'imagen de portada',
  nosotros_imagen: 'foto de Nosotros',
  ...Object.fromEntries(CAMPOS_FOTOS_INSTAGRAM.map((campo, indice) => [campo, `foto ${indice + 1} de Instagram`]))
};

const TIPOS_IMAGEN = ['image/jpeg', 'image/png', 'image/webp'];
const MAXIMO_BYTES = 5 * 1024 * 1024;
const MAX_VIDEO_BYTES = 10 * 1024 * 1024;

const sinCampo = (objeto, campo) => {
  const copia = { ...objeto };
  delete copia[campo];
  return copia;
};

// Textos y botón de una foto del carrusel (domain/banner.py). Una foto que llega sin los suyos (o una nueva)
// parte con los textos generales de la portada; los textos viajan con su foto al reordenar
export const DESTINO_POR_DEFECTO = 'CATALOGO';
export const TEXTOS_FOTO = {
  antetitulo: { etiqueta: 'Antetítulo', maximo: 200 },
  titulo: { etiqueta: 'Título', maximo: 300, obligatorio: true },
  texto: { etiqueta: 'Texto de la foto', maximo: 1000 },
};
const textosDePortada = (conf) => ({
  antetitulo: conf?.subtitulo_bienvenida ?? '', titulo: conf?.texto_bienvenida ?? '', texto: conf?.texto_landing ?? '',
  destino: DESTINO_POR_DEFECTO,
});
const textosDeFoto = (foto, conf) => (foto?.titulo
  ? { antetitulo: foto.antetitulo ?? '', titulo: foto.titulo, texto: foto.texto ?? '', destino: foto.destino || DESTINO_POR_DEFECTO }
  : textosDePortada(conf));

export const obtenerBannersIniciales = (conf) => {
  if (conf?.banners && Array.isArray(conf.banners) && conf.banners.length > 0) {
    return conf.banners.map((b, i) => ({ id: b.id, imagen: b.imagen, video: b.video || null, orden: b.orden ?? i, ...textosDeFoto(b, conf) }));
  }
  if (conf?.banner || conf?.banner_url?.trim()) {
    return [{ id: 'legacy', imagen: conf.banner || conf.banner_url.trim(), orden: 0, ...textosDePortada(conf) }];
  }
  return [];
};

// Lo que cuenta como cambio en el carrusel: el orden de las fotos y los textos de cada una
const firmaBanners = (lista) => JSON.stringify(lista.map((b) => [b.id || b.imagen, b.antetitulo, b.titulo, b.texto, b.destino, b.video || Boolean(b.videoArchivo)]));

const textosDe = (configuracion) =>
  Object.fromEntries(Object.keys(CAMPOS_TEXTO).map((campo) => [campo, configuracion?.[campo] ?? '']));

// [{ tipo, id }]: el id siempre como texto, igual que lo guarda el backend
const destacadosDe = (configuracion) => (Array.isArray(configuracion?.destacados) ? configuracion.destacados : [])
  .map(({ tipo, id }) => ({ tipo, id: String(id) }));
const mismaSeleccion = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// Convierte los errores del backend ({campo: ['mensaje']}) en un texto por campo
const erroresDe = (error) => {
  const datos = error?.response?.data;
  if (!datos || typeof datos !== 'object') return { general: 'No se pudieron guardar los cambios. Inténtalo de nuevo.' };
  return Object.fromEntries(Object.entries(datos).map(([campo, mensajes]) => [
    ['banner_orden', 'banner_fotos', 'banner_videos'].includes(campo) ? 'banner' : campo,
    [].concat(mensajes).join(' '),
  ]));
};

/**
 * Borrador de la landing en modo edición. Nada se publica hasta guardar().
 * - textos: null fuera del modo edición.
 * - imagenes: { campo: { archivo: File | null, vistaPrevia } }; archivo null = quitar la imagen.
 * - destacados: la selección de la vitrina en orden ([{ tipo, id }]); null fuera del modo edición.
 */
export default function useEdicionLanding(configuracion) {
  const [textos, setTextos] = useState(null);
  const [imagenes, setImagenes] = useState({});
  const [banners, setBanners] = useState(null);
  const [videoBannerActivo, setVideoBannerActivo] = useState(null);
  // La foto del carrusel que se está viendo y editando
  const [fotoEditada, setFotoEditada] = useState(0);
  const [destacados, setDestacados] = useState(null);
  const [menu, setMenu] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [errores, setErrores] = useState({});
  const [mensaje, setMensaje] = useState('');
  const vistasPrevias = useRef(new Set());

  const editando = textos !== null;
  const original = textosDe(configuracion);
  const textosCambiados = editando
    ? Object.keys(CAMPOS_TEXTO).filter((campo) => textos[campo] !== original[campo])
    : [];
  const bannersIniciales = obtenerBannersIniciales(configuracion);
  const bannersCambiados = Boolean(banners !== null && firmaBanners(banners) !== firmaBanners(bannersIniciales));

  const destacadosCambiados = editando && destacados !== null && !mismaSeleccion(destacados, destacadosDe(configuracion));
  const menuCambiado = editando && JSON.stringify(menu) !== JSON.stringify(configuracion?.menu_principal || {});
  const videoCambiado = videoBannerActivo !== null && videoBannerActivo !== Boolean(configuracion?.video_banner_activo);
  const hayCambios = videoCambiado || textosCambiados.length > 0 || Object.keys(imagenes).length > 0 || bannersCambiados || destacadosCambiados || menuCambiado;

  const liberarVistasPrevias = () => {
    vistasPrevias.current.forEach((url) => URL.revokeObjectURL(url));
    vistasPrevias.current.clear();
  };

  // Al salir de la página se liberan las vistas previas que queden
  useEffect(() => liberarVistasPrevias, []);

  const iniciar = () => {
    setTextos(textosDe(configuracion));
    setBanners(obtenerBannersIniciales(configuracion));
    setVideoBannerActivo(Boolean(configuracion?.video_banner_activo));
    setFotoEditada(0);
    setDestacados(destacadosDe(configuracion));
    setMenu(configuracion?.menu_principal || {});
    setErrores({});
    setMensaje('');
  };

  const cambiarTexto = (campo, valor) => {
    setTextos((actual) => ({ ...actual, [campo]: valor }));
    setErrores((actual) => sinCampo(actual, campo));
    setMensaje('');
  };

  const cambiarMenu = (valor) => {
    setMenu(valor);
    setErrores((actual) => sinCampo(actual, 'menu_principal'));
    setMensaje('');
  };

  const cambiarImagen = (campo, archivo) => {
    if (archivo && !TIPOS_IMAGEN.includes(archivo.type)) {
      setErrores((actual) => ({ ...actual, [campo]: 'Solo se admiten imágenes JPEG, PNG o WebP.' }));
      return;
    }
    if (archivo && archivo.size > MAXIMO_BYTES) {
      setErrores((actual) => ({ ...actual, [campo]: 'La imagen pesa más de 5 MB.' }));
      return;
    }
    const vistaPrevia = archivo ? URL.createObjectURL(archivo) : null;
    if (vistaPrevia) vistasPrevias.current.add(vistaPrevia);
    if (campo === 'banner') {
      if (archivo) {
        setBanners([{ id: 'nuevo_banner', archivo, vistaPrevia, imagen: vistaPrevia, ...textosDePortada(textos) }]);
      } else {
        setBanners([]);
      }
      setFotoEditada(0);
      setErrores((actual) => sinCampo(actual, campo));
      setMensaje('');
      return;
    }
    setImagenes((actual) => ({ ...actual, [campo]: { archivo, vistaPrevia } }));

    setErrores((actual) => sinCampo(actual, campo));
    setMensaje('');
  };

  // Las fotos y el video comparten el máximo de diapositivas (domain/banner.py)
  const MAX_FOTOS_BANNER = MAX_DIAPOSITIVAS_BANNER;

  const agregarFotosBanner = (nuevosArchivos) => {
    const lista = Array.from(nuevosArchivos || []);
    if (!lista.length) return;

    const base = banners ?? obtenerBannersIniciales(configuracion);
    if (base.length >= MAX_FOTOS_BANNER) {
      setErrores((actual) => ({ ...actual, banner: `No puedes subir más de ${MAX_FOTOS_BANNER} fotos al banner.` }));
      return;
    }
    if (base.length + lista.length > MAX_FOTOS_BANNER) {
      setErrores((actual) => ({
        ...actual,
        banner: `Solo puedes agregar ${MAX_FOTOS_BANNER - base.length} foto(s) más (máximo ${MAX_FOTOS_BANNER}).`,
      }));
      return;
    }

    for (const archivo of lista) {
      if (!TIPOS_IMAGEN.includes(archivo.type)) {
        setErrores((actual) => ({ ...actual, banner: 'Solo se admiten imágenes JPEG, PNG o WebP.' }));
        return;
      }
      if (archivo.size > MAXIMO_BYTES) {
        setErrores((actual) => ({ ...actual, banner: 'La imagen pesa más de 5 MB.' }));
        return;
      }
    }

    const agregados = lista.map((archivo) => {
      const vistaPrevia = URL.createObjectURL(archivo);
      vistasPrevias.current.add(vistaPrevia);
      return {
        id: `nuevo_${Math.random().toString(36).slice(2, 9)}`,
        archivo,
        vistaPrevia,
        imagen: vistaPrevia,
        // Una foto nueva parte con los textos de la portada, para que el admin los cambie
        ...textosDePortada(textos),
      };
    });

    setBanners((actual) => {
      const baseActual = actual ?? obtenerBannersIniciales(configuracion);
      return [...baseActual, ...agregados];
    });
    setErrores((actual) => sinCampo(actual, 'banner'));
    setMensaje('');
  };

  const agregarVideoBanner = (videoArchivo, portadaArchivo) => {
    const base = banners ?? obtenerBannersIniciales(configuracion);
    if (base.length >= MAX_DIAPOSITIVAS_BANNER) {
      setErrores((actual) => ({ ...actual, banner: `El carrusel admite como máximo ${MAX_DIAPOSITIVAS_BANNER} diapositivas.` }));
      return;
    }
    if (base.some((foto) => foto.video || foto.videoArchivo)) {
      setErrores((actual) => ({ ...actual, banner: 'El carrusel admite como máximo un video.' }));
      return;
    }
    if (!videoArchivo || videoArchivo.type !== 'video/mp4' || !/\.mp4$/i.test(videoArchivo.name)) {
      setErrores((actual) => ({ ...actual, banner: 'El video debe ser MP4 (.mp4).' }));
      return;
    }
    if (!videoArchivo.size || videoArchivo.size > MAX_VIDEO_BYTES) {
      setErrores((actual) => ({ ...actual, banner: 'El video debe pesar entre 1 byte y 10 MB.' }));
      return;
    }
    if (!portadaArchivo || !TIPOS_IMAGEN.includes(portadaArchivo.type) || !portadaArchivo.size || portadaArchivo.size > MAXIMO_BYTES) {
      setErrores((actual) => ({ ...actual, banner: 'El video necesita una imagen de portada JPEG, PNG o WebP de hasta 5 MB.' }));
      return;
    }
    const vistaPrevia = URL.createObjectURL(portadaArchivo);
    vistasPrevias.current.add(vistaPrevia);
    setBanners([...base, {
      id: `nuevo_video_${Date.now()}`, archivo: portadaArchivo, videoArchivo,
      imagen: vistaPrevia, vistaPrevia, video: null, ...textosDePortada(textos),
    }]);
    setFotoEditada(base.length);
    setErrores((actual) => sinCampo(actual, 'banner'));
    setMensaje('');
  };

  const reordenarFotosBanner = (origen, destino) => {
    const total = (banners ?? obtenerBannersIniciales(configuracion)).length;
    if (origen < 0 || origen >= total || destino < 0 || destino >= total) return;
    setBanners((actual) => {
      const base = [...(actual ?? obtenerBannersIniciales(configuracion))];
      const [movido] = base.splice(origen, 1);
      base.splice(destino, 0, movido);
      return base;
    });
    // La foto que se mueve queda a la vista, con sus textos
    setFotoEditada(destino);
    setMensaje('');
  };

  const eliminarFotoBanner = (indice) => {
    const total = (banners ?? obtenerBannersIniciales(configuracion)).length;
    if (indice < 0 || indice >= total) return;
    setBanners((actual) => {
      const base = [...(actual ?? obtenerBannersIniciales(configuracion))];
      const eliminado = base[indice];
      if (eliminado?.vistaPrevia) {
        URL.revokeObjectURL(eliminado.vistaPrevia);
        vistasPrevias.current.delete(eliminado.vistaPrevia);
      }
      base.splice(indice, 1);
      return base;
    });
    setFotoEditada((actual) => Math.max(0, Math.min(actual > indice ? actual - 1 : actual, total - 2)));
    setMensaje('');
  };

  // Elegir qué foto del carrusel se ve y se edita
  const seleccionarFoto = (indice) => {
    const total = (banners ?? obtenerBannersIniciales(configuracion)).length;
    if (indice >= 0 && indice < total) setFotoEditada(indice);
  };

  // Textos y destino del botón de la foto que se está editando
  const cambiarTextoFoto = (campo, valor) => {
    setBanners((actual) => (actual ?? obtenerBannersIniciales(configuracion))
      .map((foto, indice) => (indice === fotoEditada ? { ...foto, [campo]: valor } : foto)));
    setErrores((actual) => sinCampo(sinCampo(actual, 'banner_titulo'), 'banner_orden'));
    setMensaje('');
  };

  // Selección de destacados: agregar al final (hasta 8, sin repetir), mover un lugar y quitar
  const cambiarDestacados = (cambio) => {
    setDestacados((actual) => cambio([...(actual || [])]));
    setErrores((actual) => sinCampo(actual, 'destacados'));
    setMensaje('');
  };

  const agregarDestacado = ({ tipo, id }) => cambiarDestacados((lista) => {
    const nuevo = { tipo, id: String(id) };
    const repetido = lista.some((elegido) => elegido.tipo === nuevo.tipo && elegido.id === nuevo.id);
    return repetido || lista.length >= MAX_DESTACADOS ? lista : [...lista, nuevo];
  });

  const moverDestacado = (indice, paso) => cambiarDestacados((lista) => {
    const destino = indice + paso;
    if (indice < 0 || destino < 0 || indice >= lista.length || destino >= lista.length) return lista;
    [lista[indice], lista[destino]] = [lista[destino], lista[indice]];
    return lista;
  });

  const quitarDestacado = (indice) => cambiarDestacados((lista) => lista.filter((_, posicion) => posicion !== indice));

  const descartar = () => {
    liberarVistasPrevias();
    setImagenes({});
    setTextos(textosDe(configuracion));
    setBanners(obtenerBannersIniciales(configuracion));
    setVideoBannerActivo(Boolean(configuracion?.video_banner_activo));
    setFotoEditada(0);
    setDestacados(destacadosDe(configuracion));
    setMenu(configuracion?.menu_principal || {});
    setErrores({});
    setMensaje('');
  };

  const salir = () => {
    liberarVistasPrevias();
    setImagenes({});
    setTextos(null);
    setBanners(null);
    setFotoEditada(0);
    setDestacados(null);
    setMenu(null);
    setErrores({});
    setMensaje('');
  };

  const guardar = async () => {
    // Con fotos en el carrusel, los textos de la portada se editan en cada foto (los generales siguen a la primera)
    const fotos = banners ?? obtenerBannersIniciales(configuracion);
    const camposPortada = fotos.length ? ['subtitulo_bienvenida', 'texto_bienvenida', 'texto_landing'] : [];
    const faltantes = Object.entries(CAMPOS_TEXTO)
      .filter(([campo, { obligatorio }]) => obligatorio && !camposPortada.includes(campo) && !textos[campo].trim())
      .map(([campo]) => [campo, 'No puede quedar vacío.']);
    if (faltantes.length) {
      setErrores(Object.fromEntries(faltantes));
      return;
    }
    // Cada foto necesita su título (es el h1 de la portada): se muestra la primera que no lo tiene
    const sinTitulo = fotos.findIndex((foto) => !foto.titulo?.trim());
    if (sinTitulo >= 0) {
      setFotoEditada(sinTitulo);
      setErrores({ banner_titulo: `La foto ${sinTitulo + 1} necesita un título.` });
      return;
    }

    setGuardando(true);
    setErrores({});
    try {
      const nuevas = Object.entries(imagenes).filter(([campo, { archivo }]) => campo !== 'banner' && archivo);
      const quitadas = Object.fromEntries(
        Object.entries(imagenes).filter(([campo, { archivo }]) => campo !== 'banner' && !archivo).map(([campo]) => [campo, null]));
      const textosNuevos = Object.fromEntries(textosCambiados.map((campo) => [campo, textos[campo]]));
      if (menuCambiado) textosNuevos.menu_principal = menu;
      if (videoCambiado) textosNuevos.video_banner_activo = videoBannerActivo;

      // Banners
      const bannersActuales = banners ?? obtenerBannersIniciales(configuracion);
      const nuevosArchivosBanner = bannersActuales.filter((b) => b.archivo).map((b) => b.archivo);
      const nuevosVideosBanner = bannersActuales.filter((b) => b.videoArchivo).map((b) => b.videoArchivo);
      let manifestBanners = null;
      if (bannersCambiados) {
        // Cada foto viaja con su referencia y sus textos (application/banner.py)
        manifestBanners = bannersActuales.map((b) => ({
          ...(b.videoArchivo ? { video_indice: nuevosVideosBanner.indexOf(b.videoArchivo) } : {}),
          ref: b.archivo ? `nuevo:${nuevosArchivosBanner.indexOf(b.archivo)}` : `id:${b.id}`,
          antetitulo: b.antetitulo, titulo: b.titulo, texto: b.texto, destino: b.destino,
        }));
      }

      const hayArchivos = nuevas.length > 0 || nuevosArchivosBanner.length > 0 || nuevosVideosBanner.length > 0;
      if (hayArchivos) {
        const formulario = new FormData();
        Object.entries(textosNuevos).forEach(([campo, valor]) => formulario.append(campo, typeof valor === 'object' ? JSON.stringify(valor) : valor));
        nuevas.forEach(([campo, { archivo }]) => formulario.append(campo, archivo));
        if (destacadosCambiados) formulario.append('destacados', JSON.stringify(destacados));
        nuevosArchivosBanner.forEach((arch) => formulario.append('banner_fotos', arch));
        nuevosVideosBanner.forEach((arch) => formulario.append('banner_videos', arch));
        if (manifestBanners !== null) {
          formulario.append('banner_orden', JSON.stringify(manifestBanners));
        }
        await clienteAxios.patch('configuracion/negocio/', formulario, { headers: { 'Content-Type': undefined } });
      }

      const enJson = hayArchivos ? quitadas : { ...textosNuevos, ...quitadas, ...(destacadosCambiados ? { destacados } : {}) };
      if (manifestBanners !== null && !hayArchivos) {
        enJson.banner_orden = JSON.stringify(manifestBanners);
      }
      if (Object.keys(enJson).length) await clienteAxios.patch('configuracion/negocio/', enJson);

      const guardada = await recargarConfiguracion();
      liberarVistasPrevias();
      setImagenes({});
      setTextos(textosDe(guardada));
      setBanners(obtenerBannersIniciales(guardada));
      setVideoBannerActivo(Boolean(guardada.video_banner_activo));
      setFotoEditada((actual) => Math.min(actual, Math.max(0, obtenerBannersIniciales(guardada).length - 1)));
      setDestacados(destacadosDe(guardada));
      setMenu(guardada?.menu_principal || {});
      setMensaje('Cambios guardados: ya están publicados en tu tienda.');
    } catch (error) {
      setErrores(erroresDe(error));
    } finally {
      setGuardando(false);
    }
  };

  // Lo que se dibuja: la configuración publicada con el borrador encima
  const listaBannersVista = (banners ?? obtenerBannersIniciales(configuracion)).map((b) => ({
    ...b,
    imagen: b.vistaPrevia || b.imagen,
  }));

  const vista = editando
    ? {
        ...configuracion,
        ...textos,
        menu_principal: menu,
        ...Object.fromEntries(Object.entries(imagenes).map(([campo, { vistaPrevia }]) => [campo, vistaPrevia])),
        banners: listaBannersVista,
        video_banner_activo: videoBannerActivo,
      }
    : configuracion;

  return {
    editando, vista, textos, destacados, menu, hayCambios, guardando, errores, mensaje,
    videoBannerActivo, cambiarVideoBannerActivo: setVideoBannerActivo, agregarVideoBanner,
    banners: listaBannersVista,
    fotoEditada: Math.min(fotoEditada, Math.max(0, listaBannersVista.length - 1)),
    iniciar, cambiarTexto, cambiarImagen, agregarFotosBanner, reordenarFotosBanner, eliminarFotoBanner,
    seleccionarFoto, cambiarTextoFoto,
    agregarDestacado, moverDestacado, quitarDestacado, cambiarMenu,
    descartar, salir, guardar
  };
}
