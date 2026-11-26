import { useEffect, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import Estrellas from './Estrellas';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoLista } from './carga/EsqueletosPanel';

// Moderación de reseñas: llegan pendientes y solo se publican las aprobadas. El admin no puede crearlas ni
// editarlas, así el promedio de la tienda es real
const FILTROS = [
  ['PENDIENTE', 'Pendientes'],
  ['APROBADA', 'Aprobadas'],
  ['OCULTA', 'Ocultas']
];

const VACIO = {
  PENDIENTE: 'No hay reseñas por revisar.',
  APROBADA: 'Todavía no apruebas ninguna reseña.',
  OCULTA: 'No hay reseñas ocultas.'
};

// Igual que PaginacionResenas en el backend
const POR_PAGINA = 20;

const formatearFecha = (iso) => new Date(iso).toLocaleString('es-CL', { dateStyle: 'medium', timeStyle: 'short' });

export default function GestorResenas() {
  // `version` vuelve a pedir la misma página después de moderar
  const [filtro, setFiltro] = useState({ estado: 'PENDIENTE', pagina: 1, version: 0 });
  // A qué filtro corresponde lo cargado: si no coincide con el pedido, aún está cargando
  const [cargada, setCargada] = useState({ filtro: null, resenas: [], total: 0 });
  const [aviso, setAviso] = useState(null);
  const [enCurso, setEnCurso] = useState(null);

  useEffect(() => {
    let vigente = true;
    clienteAxios.get('ventas/admin/resenas/', { params: { estado: filtro.estado, pagina: filtro.pagina } })
      .then(({ data }) => {
        if (vigente) setCargada({ filtro, resenas: data.results, total: data.count });
      })
      .catch((error) => {
        if (!vigente) return;
        // Al moderar la última reseña de una página, esa página deja de existir (404): se vuelve a la anterior
        if (error.response?.status === 404 && filtro.pagina > 1) {
          setFiltro(actual => ({ ...actual, pagina: actual.pagina - 1 }));
          return;
        }
        setAviso({ tipo: 'error', texto: 'No se pudieron cargar las reseñas.' });
        setCargada({ filtro, resenas: [], total: 0 });
      });
    return () => { vigente = false; };
  }, [filtro]);

  // Tras moderar (cambia solo `version`) la lista sigue a la vista mientras se recarga, sin acciones
  const recargando = cargada.filtro !== filtro;
  const cargando = !cargada.filtro || cargada.filtro.estado !== filtro.estado
    || cargada.filtro.pagina !== filtro.pagina;
  const ocupada = (resena) => recargando || enCurso === resena.id;
  const paginas = Math.ceil(cargada.total / POR_PAGINA);

  const elegirEstado = (estado) => {
    setAviso(null);
    setFiltro({ estado, pagina: 1, version: 0 });
  };

  const irA = (pagina) => {
    setAviso(null);
    setFiltro(actual => ({ ...actual, pagina }));
  };

  const moderar = async (resena, estado) => {
    setEnCurso(resena.id);
    setAviso(null);
    try {
      await clienteAxios.patch(`ventas/admin/resenas/${resena.id}/`, { estado });
      setAviso({ tipo: 'exito', texto: estado === 'APROBADA'
        ? `Publicaste la reseña de ${resena.nombre_publico}.`
        : `Ocultaste la reseña de ${resena.nombre_publico}: ya no se ve en la tienda.` });
      // La reseña pasa a otra pestaña: se recarga la página actual
      setFiltro(actual => ({ ...actual, version: actual.version + 1 }));
    } catch (error) {
      const detalle = error.response?.data?.estado?.[0];
      setAviso({ tipo: 'error', texto: detalle || `No se pudo moderar la reseña de ${resena.nombre_publico}.` });
    } finally {
      setEnCurso(null);
    }
  };

  return (
    <>
      <p className="texto-secundario admin-descripcion">
        Tus clientes califican la tienda y los productos cuando reciben su pedido. Revisa cada reseña antes de
        publicarla: las aprobadas aparecen en la página de inicio y en la ficha del producto, y cuentan en el
        promedio. Se activan en Configuración &gt; Reseñas de Clientes.
      </p>

      <div role="group" aria-label="Mostrar reseñas" className="publicacion-acciones resenas-filtros">
        {FILTROS.map(([estado, etiqueta]) => (
          <button key={estado} type="button" className="boton boton-contorno" aria-pressed={filtro.estado === estado}
            onClick={() => elegirEstado(estado)}>
            {etiqueta}
          </button>
        ))}
      </div>

      {aviso && (
        <p role={aviso.tipo === 'error' ? 'alert' : 'status'} className={`admin-aviso admin-aviso--${aviso.tipo}`}>
          {aviso.texto}
        </p>
      )}

      {cargando ? (
        <Cargando texto="Cargando reseñas..."><EsqueletoLista /></Cargando>
      ) : cargada.resenas.length === 0 ? (
        <p className="texto-secundario">{VACIO[filtro.estado]}</p>
      ) : (
        <ul className="lista-sin-estilo cotizaciones-lista">
          {cargada.resenas.map(r => (
            <li key={r.id} className="cotizacion-tarjeta">
              <article aria-labelledby={`resena-${r.id}-titulo`}>
                <div className="cotizacion-tarjeta-encabezado">
                  <h3 id={`resena-${r.id}-titulo`}>{r.nombre_publico} · Pedido #{r.orden_id}</h3>
                  <span className={`blog-admin-estado${r.estado === 'APROBADA' ? ' blog-admin-estado--publicada' : ''}`}>
                    {r.estado_display}
                  </span>
                </div>
                <p className="texto-secundario cotizacion-tarjeta-fecha">Recibida el {formatearFecha(r.fecha_creacion)}</p>
                <dl className="cotizacion-tarjeta-datos">
                  {[{ clave: 'tienda', titulo: 'La tienda', estrellas: r.estrellas, comentario: r.comentario },
                    ...r.productos.map(p => ({ clave: p.producto_mongo_id, titulo: p.producto_nombre,
                      estrellas: p.estrellas, comentario: p.comentario }))
                  ].map(c => (
                    <div key={c.clave} className="resena-calificacion">
                      <dt>{c.titulo}</dt>
                      <dd>
                        <Estrellas valor={c.estrellas} />
                        {c.comentario && <span className="resena-comentario">{c.comentario}</span>}
                      </dd>
                    </div>
                  ))}
                </dl>
                <div className="publicacion-acciones resena-acciones">
                  {r.estado !== 'APROBADA' && (
                    <button type="button" className="boton boton-primario" disabled={ocupada(r)}
                      aria-label={`Aprobar la reseña de ${r.nombre_publico}`} onClick={() => moderar(r, 'APROBADA')}>
                      Aprobar
                    </button>
                  )}
                  {r.estado !== 'OCULTA' && (
                    <button type="button" className="boton boton-contorno" disabled={ocupada(r)}
                      aria-label={`Ocultar la reseña de ${r.nombre_publico}`} onClick={() => moderar(r, 'OCULTA')}>
                      Ocultar
                    </button>
                  )}
                </div>
              </article>
            </li>
          ))}
        </ul>
      )}

      {!cargando && paginas > 1 && (
        <nav className="publicacion-acciones cotizaciones-paginacion" aria-label="Páginas de reseñas">
          <button type="button" className="boton boton-contorno" disabled={filtro.pagina === 1}
            onClick={() => irA(filtro.pagina - 1)}>
            <span aria-hidden="true">←</span> Anteriores
          </button>
          <span className="texto-secundario">Página {filtro.pagina} de {paginas}</span>
          <button type="button" className="boton boton-contorno" disabled={filtro.pagina === paginas}
            onClick={() => irA(filtro.pagina + 1)}>
            Siguientes <span aria-hidden="true">→</span>
          </button>
        </nav>
      )}
    </>
  );
}
