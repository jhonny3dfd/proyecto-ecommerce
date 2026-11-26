import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import clienteAxios from "../components/auth/axiosConfig";
import Header from "../components/header/header";
import Portada from "../components/landing/Portada";
import SeccionProductos from "../components/landing/SeccionProductos";
import SeccionDestacados from "../components/landing/SeccionDestacados";
import EditorVitrina from "../components/landing/EditorVitrina";
import SeccionNosotros from "../components/landing/SeccionNosotros";
import SeccionInstagram from "../components/landing/SeccionInstagram";
import SeccionResenas from "../components/landing/SeccionResenas";
import useResenas from "../hooks/useResenas";
import BarraEdicion from "../components/landing/BarraEdicion";
import useConfiguracionTienda from "../hooks/useConfiguracionTienda";
import useEdicionLanding from "../hooks/useEdicionLanding";
import "../components/landing/landing.css";
import { EsqueletoPortada } from "../components/carga/EsqueletosTienda";

const NOTA_PRODUCTOS = "Esta sección se llena sola con tus productos publicados.";

// RF-01.1: la raíz del dominio muestra la landing (nunca el catálogo directo). El admin la edita en su mismo
// lugar (modo edición); los productos salen de la vitrina (más vendidos o destacados, y últimos agregados).
function LandingPage({ onMarcaTemporal }) {
  const configuracion = useConfiguracionTienda();
  const edicion = useEdicionLanding(configuracion);
  // null mientras carga: así se sabe cuándo ya están dibujadas las secciones de productos
  const [vitrina, setVitrina] = useState(null);
  const resenasActivas = configuracion ? Boolean(configuracion.resenas_activas) : undefined;
  const resenas = useResenas("ventas/resenas/tienda/", resenasActivas);
  const { hash } = useLocation();
  const [parametros, setParametros] = useSearchParams();
  // El rol solo decide si se ofrece el botón; quien de verdad autoriza los cambios es el backend
  const esAdmin = localStorage.getItem("rol") === "ADMIN";
  // Si la configuración no cargó (ej. el servidor responde con error), llega {}: el editor partiría vacío y
  // guardarlo pisaría los textos reales de la tienda. La configuración real siempre trae nombre_tienda
  const configuracionCargada = Boolean(configuracion) && "nombre_tienda" in configuracion;

  const cargarVitrina = useCallback(() => {
    clienteAxios.get("catalogo/vitrina/")
      .then(({ data }) => setVitrina(data))
      .catch((error) => {
        console.error("No se pudieron cargar los productos de la portada:", error);
        setVitrina({ mas_vendidos: [], recientes: [] });
      });
  }, []);

  useEffect(cargarVitrina, [cargarVitrina]);

  // Al guardar en el modo edición se recarga la configuración, no la vitrina: si cambió el modo (Más vendidos o
  // Destacados), la selección o su título, se vuelve a pedir para que la landing lo muestre sin recargar la página
  const firmaVitrina = configuracion
    ? JSON.stringify([configuracion.vitrina_modo, configuracion.destacados, configuracion.destacados_titulo])
    : null;
  const firmaAnterior = useRef(null);
  useEffect(() => {
    if (firmaVitrina === null) return;
    if (firmaAnterior.current !== null && firmaAnterior.current !== firmaVitrina) cargarVitrina();
    firmaAnterior.current = firmaVitrina;
  }, [firmaVitrina, cargarVitrina]);

  // El enlace "Nosotros" del header lleva a /#nosotros. Se baja cuando ya está todo lo de arriba (portada y
  // productos y reseñas); si no, el contenido que llega después corre la sección
  useEffect(() => {
    if (!hash || !configuracion || !vitrina || !resenas) return;
    document.getElementById(hash.slice(1))?.scrollIntoView();
  }, [hash, configuracion, vitrina, resenas]);

  // El panel abre la landing directo en modo edición con /?editar=1. Se abre una sola vez, en el render (no en
  // un efecto), apenas llega la configuración
  const [abrirEdicion, setAbrirEdicion] = useState(() => parametros.get("editar") === "1");
  if (abrirEdicion && configuracion) {
    setAbrirEdicion(false);
    if (esAdmin && configuracionCargada) edicion.iniciar();
  }

  // Se quita ?editar=1 de la URL, para que recargar la página no vuelva a abrir el modo edición
  useEffect(() => {
    if (parametros.has("editar")) setParametros({}, { replace: true });
  }, [parametros, setParametros]);

  // Con cambios sin guardar se avisa antes de cerrar la pestaña o de seguir un enlace
  useEffect(() => {
    if (!edicion.hayCambios) return;
    const alSalir = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    const alHacerClic = (e) => {
      const enlace = e.target.closest?.("a[href]");
      if (enlace && !window.confirm("Tienes cambios sin guardar en la página de inicio. ¿Salir y descartarlos?")) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", alSalir);
    document.addEventListener("click", alHacerClic, true);
    return () => {
      window.removeEventListener("beforeunload", alSalir);
      document.removeEventListener("click", alHacerClic, true);
    };
  }, [edicion.hayCambios]);

  const vista = edicion.vista;
  // Destacados en lugar de "Más vendidos": la vitrina solo los trae si el admin los eligió y queda alguno visible.
  // Mientras carga se usa el modo guardado, para no mostrar un instante el título equivocado
  const conDestacados = vitrina ? vitrina.destacados?.length > 0 : configuracion?.vitrina_modo === "DESTACADOS";
  // El footer está fuera de la landing (App.jsx): en modo edición recibe el borrador del nombre y de los logos
  useEffect(() => {
    onMarcaTemporal?.(edicion.editando ? {
      nombre_tienda: vista?.nombre_tienda ?? '', logo: vista?.logo,
      ubicacion_logo_universidad: vista?.ubicacion_logo_universidad,
      menu_principal: vista?.menu_principal,
    } : null);
  }, [edicion.editando, vista?.nombre_tienda, vista?.logo, vista?.ubicacion_logo_universidad, vista?.menu_principal, onMarcaTemporal]);

  useEffect(() => {
    return () => onMarcaTemporal?.(null);
  }, [onMarcaTemporal]);

  return (
    <>
      <Header vistaPrevia={edicion.editando ? {
        nombre_tienda: vista.nombre_tienda, logo: vista.logo, ubicacion_logo_universidad: vista.ubicacion_logo_universidad,
        menu_principal: vista.menu_principal,
      } : undefined} edicion={edicion} />
      <main tabIndex={-1} id="contenido" className={edicion.editando ? "landing--editando" : undefined}>
        {configuracion ? (
          <>
            {edicion.editando && (
              <div className="contenedor landing-nombre-edicion">
                <CampoNombreTienda edicion={edicion} />
              </div>
            )}
            <Portada configuracion={vista} edicion={edicion} />
            {edicion.editando ? (
              <EditorVitrina edicion={edicion} vitrina={vitrina} configuracion={configuracion} nota={NOTA_PRODUCTOS} />
            ) : conDestacados ? (
              <SeccionDestacados titulo={vitrina?.destacados_titulo || configuracion.destacados_titulo}
                destacados={vitrina?.destacados} cargando={!vitrina} nombreBlog={configuracion.blog_nombre} />
            ) : (
              <SeccionProductos id="mas-vendidos" antetitulo="Lo más elegido" titulo="Más vendidos"
                productos={vitrina?.mas_vendidos} cargando={!vitrina} alterna />
            )}
            <SeccionProductos id="recientes" antetitulo="Recién llegados" titulo="Últimos agregados"
              productos={vitrina?.recientes} cargando={!vitrina} etiqueta="Nuevo"
              nota={edicion.editando ? NOTA_PRODUCTOS : undefined} />
            <SeccionResenas resumen={resenas} activas={resenasActivas} edicion={edicion} />
            <SeccionNosotros configuracion={vista} edicion={edicion} />
            <SeccionInstagram configuracion={vista} edicion={edicion} />
          </>
        ) : (
          // Mientras llega la configuración se reserva el espacio de la portada (sin textos de ejemplo)
          <div className="portada" aria-busy="true">
            <p className="visualmente-oculto">Cargando la tienda...</p>
            <EsqueletoPortada />
          </div>
        )}
      </main>

      {esAdmin && configuracion && (edicion.editando ? (
        <BarraEdicion edicion={edicion} />
      ) : configuracionCargada ? (
        <button type="button" className="boton boton-primario boton-editar-pagina" onClick={edicion.iniciar}>
          Editar página
        </button>
      ) : (
        <p role="alert" className="aviso-edicion-no-disponible">
          No se pudo cargar la configuración de la tienda, así que por ahora no se puede editar la página.
          Recarga en un momento; si sigue igual, revisa que el servidor esté funcionando.
        </p>
      ))}
    </>
  );
}

// El nombre de la tienda se ve en el header y en la pestaña: en modo edición se cambia arriba de la portada
function CampoNombreTienda({ edicion }) {
  return (
    <label className="landing-nombre-campo">
      <span className="campo-editable-etiqueta">Nombre de la tienda</span>
      <input
        value={edicion.textos.nombre_tienda}
        maxLength={255}
        onChange={(e) => edicion.cambiarTexto("nombre_tienda", e.target.value)}
        aria-invalid={Boolean(edicion.errores.nombre_tienda)}
      />
    </label>
  );
}

export default LandingPage;
