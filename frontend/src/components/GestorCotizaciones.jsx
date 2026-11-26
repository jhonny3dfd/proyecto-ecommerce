import { useEffect, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import FotosCotizacion from './FotosCotizacion';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoLista } from './carga/EsqueletosPanel';

// Las solicitudes del formulario de cotización: la tienda las responde por correo o teléfono y aquí anota en qué
// quedó cada una
const ESTADOS = [
  ['NUEVA', 'Nueva'],
  ['RESPONDIDA', 'Respondida'],
  ['ACEPTADA', 'Aceptada'],
  ['DESCARTADA', 'Descartada']
];

const formatearFecha = (iso) => new Date(iso).toLocaleString('es-CL', { dateStyle: 'medium', timeStyle: 'short' });
// '2026-11-05' es una fecha sin hora: se muestra tal cual, sin pasar por la zona horaria
const formatearDia = (dia) => dia.split('-').reverse().join('-');

// Igual que PaginacionCotizaciones en el backend
const POR_PAGINA = 20;

export default function GestorCotizaciones() {
  const [cotizaciones, setCotizaciones] = useState([]);
  const [pagina, setPagina] = useState(1);
  // A qué página corresponde lo cargado: si no coincide con la pedida, aún está cargando
  const [cargada, setCargada] = useState({ pagina: null, total: 0 });
  const [aviso, setAviso] = useState(null);
  const [enCurso, setEnCurso] = useState(null);

  useEffect(() => {
    clienteAxios.get('ventas/admin/cotizaciones/', { params: { pagina } })
      .then(({ data }) => {
        setCotizaciones(data.results);
        setCargada({ pagina, total: data.count });
      })
      .catch(() => {
        setAviso({ tipo: 'error', texto: 'No se pudieron cargar las cotizaciones.' });
        setCargada((actual) => ({ ...actual, pagina }));
      });
  }, [pagina]);

  const cargando = cargada.pagina !== pagina;
  const paginas = Math.ceil(cargada.total / POR_PAGINA);
  const irA = (nueva) => {
    setAviso(null);
    setPagina(nueva);
  };

  const cambiarEstado = async (cotizacion, estado) => {
    setEnCurso(cotizacion.id);
    setAviso(null);
    try {
      const { data } = await clienteAxios.patch(`ventas/admin/cotizaciones/${cotizacion.id}/`, { estado });
      setCotizaciones(actuales => actuales.map(c => (c.id === data.id ? data : c)));
      setAviso({ tipo: 'exito', texto: `La cotización #${data.id} quedó como ${data.estado_display}.` });
    } catch {
      setAviso({ tipo: 'error', texto: `No se pudo cambiar el estado de la cotización #${cotizacion.id}.` });
    } finally {
      setEnCurso(null);
    }
  };

  if (cargando) return <Cargando texto="Cargando cotizaciones..."><EsqueletoLista /></Cargando>;

  return (
    <>
      <p className="texto-secundario admin-descripcion">
        Responde cada solicitud por correo o teléfono (basta con responder el correo que te llegó) y anota aquí en
        qué quedó. El formulario se activa en Configuración &gt; Cotizaciones y Encargos.
      </p>

      {aviso && (
        <p role={aviso.tipo === 'error' ? 'alert' : 'status'} className={`admin-aviso admin-aviso--${aviso.tipo}`}>
          {aviso.texto}
        </p>
      )}

      {cotizaciones.length === 0 ? (
        <p className="texto-secundario">Todavía no hay solicitudes de cotización.</p>
      ) : (
        <ul className="lista-sin-estilo cotizaciones-lista">
          {cotizaciones.map(c => (
            <li key={c.id} className="cotizacion-tarjeta">
              <article aria-labelledby={`cotizacion-${c.id}-titulo`}>
                <div className="cotizacion-tarjeta-encabezado">
                  <h3 id={`cotizacion-${c.id}-titulo`}>#{c.id} · {c.producto_nombre || 'Producto descrito por el cliente'}</h3>
                  <label className="cotizacion-tarjeta-estado">
                    <span className="visualmente-oculto">Estado de la cotización #{c.id}</span>
                    <select value={c.estado} disabled={enCurso === c.id}
                      onChange={(e) => cambiarEstado(c, e.target.value)}>
                      {ESTADOS.map(([valor, etiqueta]) => <option key={valor} value={valor}>{etiqueta}</option>)}
                    </select>
                  </label>
                </div>
                <p className="texto-secundario cotizacion-tarjeta-fecha">Recibida el {formatearFecha(c.fecha_creacion)}</p>
                <dl className="cotizacion-tarjeta-datos">
                  {c.descripcion && <><dt>Qué necesita</dt><dd>{c.descripcion}</dd></>}
                  <dt>Cantidad</dt><dd>{c.cantidad}</dd>
                  {c.personalizacion && <><dt>Personalización</dt><dd>{c.personalizacion}</dd></>}
                  {c.fotos?.length > 0 && (
                    <><dt>Fotos de su idea</dt><dd><FotosCotizacion cotizacionId={c.id} fotos={c.fotos} /></dd></>
                  )}
                  {c.fecha_requerida && <><dt>Lo necesita para el</dt><dd>{formatearDia(c.fecha_requerida)}</dd></>}
                  <dt>Contacto</dt>
                  <dd>
                    {c.nombre} · <a href={`mailto:${c.correo}`}>{c.correo}</a> · <a href={`tel:${c.telefono}`}>{c.telefono}</a>
                  </dd>
                  {c.datos_empresa && (
                    <>
                      <dt>Factura</dt>
                      <dd>
                        {c.datos_empresa.razon_social} · RUT {c.datos_empresa.rut} · {c.datos_empresa.giro}
                        <br />{c.datos_empresa.direccion} · {c.datos_empresa.correo}
                      </dd>
                    </>
                  )}
                </dl>
              </article>
            </li>
          ))}
        </ul>
      )}

      {paginas > 1 && (
        <nav className="publicacion-acciones cotizaciones-paginacion" aria-label="Páginas de cotizaciones">
          <button type="button" className="boton boton-contorno" disabled={pagina === 1} onClick={() => irA(pagina - 1)}>
            <span aria-hidden="true">←</span> Anteriores
          </button>
          <span className="texto-secundario">Página {pagina} de {paginas}</span>
          <button type="button" className="boton boton-contorno" disabled={pagina === paginas}
            onClick={() => irA(pagina + 1)}>
            Siguientes <span aria-hidden="true">→</span>
          </button>
        </nav>
      )}
    </>
  );
}
