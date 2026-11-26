import ListaResenas, { PromedioResenas } from '../ListaResenas';

// Reseñas de la landing: el promedio y las últimas aprobadas con comentario. Sin reseñas aprobadas no se muestra,
// salvo en modo edición, donde una nota explica de dónde salen
export default function SeccionResenas({ resumen, activas, edicion }) {
  const editando = Boolean(edicion?.editando);
  if (!resumen?.total && !editando) return null;

  return (
    <section id="resenas" className="seccion-landing seccion-landing--alterna resenas-landing"
      aria-labelledby="resenas-titulo">
      <div className="contenedor">
        <div className="resenas-landing-encabezado">
          <span className="antetitulo">Reseñas</span>
          <h2 id="resenas-titulo">Lo que dicen nuestros clientes</h2>
          {resumen?.total > 0 && <PromedioResenas promedio={resumen.promedio} total={resumen.total} />}
        </div>

        {editando && !resumen?.total && (
          <p className="seccion-landing-nota resenas-landing-nota">
            {activas
              ? 'Aquí se verán las reseñas que apruebes en el panel, en Reseñas. Mientras no haya ninguna, la sección no aparece.'
              : 'Para mostrar reseñas de tus clientes, actívalas en el panel: Configuración > Reseñas de Clientes.'}
          </p>
        )}

        {resumen?.resenas.length > 0 && <ListaResenas resenas={resumen.resenas} />}
      </div>
    </section>
  );
}
