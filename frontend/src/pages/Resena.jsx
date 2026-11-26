import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import clienteAxios from '../components/auth/axiosConfig';
import EstrellasEntrada from '../components/EstrellasEntrada';
import Header from '../components/header/header';
import useConfiguracionTienda from '../hooks/useConfiguracionTienda';
import { leerTokensDeEnlace, olvidarTokensDeEnlace } from '../utils/enlacesConToken';
import '../components/Checkout.css';
import './Resena.css';
import Spinner from '../components/carga/Spinner';

const RUTA = '/resena';

// Igual que domain/resenas.py
const LARGO_COMENTARIO = 1000;
const LARGO_NOMBRE = 40;

// El backend responde { campo: mensaje | [mensajes] } y los de cada producto anidados en 'productos'
const comoTexto = (mensajes) => [].concat(mensajes).join(' ');

// Reseña de un pedido entregado, desde el enlace firmado del correo (/resena?t=...): estrellas para la tienda
// (obligatorias) y para cada producto (opcionales). Llega pendiente: la tienda la aprueba antes de publicarla
export default function Resena() {
  const configuracion = useConfiguracionTienda();
  const [parametros] = useSearchParams();
  // main.jsx ya sacó el token de la URL del correo, y Mis pedidos lo guarda antes de abrir esta página; el ?t= de
  // la URL queda solo como respaldo
  const [token] = useState(() => leerTokensDeEnlace(RUTA)?.t || parametros.get('t') || '');
  // { estado: 'cargando' | 'error' | 'formulario' | 'enviada', ... }
  const [vista, setVista] = useState(token ? { estado: 'cargando' } : {
    estado: 'error', texto: 'El enlace para dejar la reseña no es válido o ya venció.'
  });
  const [estrellas, setEstrellas] = useState(null);
  const [comentario, setComentario] = useState('');
  const [nombre, setNombre] = useState('');
  const [productos, setProductos] = useState({});
  const [acepta, setAcepta] = useState(false);
  const [errores, setErrores] = useState({});
  const [aviso, setAviso] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const agradecimiento = useRef(null);

  useEffect(() => {
    if (!token) return;
    clienteAxios.get('ventas/resenas/formulario/', { params: { t: token } })
      .then(({ data }) => {
        setNombre(data.nombre_sugerido);
        setVista({ estado: 'formulario', pedido: data });
      })
      .catch((error) => setVista({ estado: 'error', texto: error.response?.data?.detail
        || 'No pudimos abrir el formulario. Inténtalo de nuevo en un rato.' }));
  }, [token]);

  useEffect(() => {
    if (vista.estado !== 'enviada') return;
    // El formulario era largo: se vuelve al título y el foco queda en el agradecimiento
    document.documentElement.scrollTop = 0;
    agradecimiento.current?.focus({ preventScroll: true });
  }, [vista.estado]);

  const tienda = configuracion?.nombre_tienda || 'la tienda';

  const editarProducto = (productoId, cambios) => {
    setProductos(actuales => ({ ...actuales, [productoId]: { ...actuales[productoId], ...cambios } }));
    setErrores(actuales => ({ ...actuales, productos: { ...actuales.productos, [productoId]: undefined } }));
  };

  const enviar = async (e) => {
    e.preventDefault();
    setAviso(null);
    if (!estrellas) {
      setErrores(actuales => ({ ...actuales, estrellas: `Elige cuántas estrellas le das a ${tienda}.` }));
      setAviso({ tipo: 'error', texto: 'Revisa los datos marcados.' });
      document.querySelector('input[name="resena-tienda"]')?.focus();
      return;
    }
    setEnviando(true);
    try {
      const { data } = await clienteAxios.post('ventas/resenas/', {
        token, estrellas, comentario, nombre_publico: nombre, acepta_publicacion: acepta,
        // Solo los productos que calificó o comentó
        productos: Object.entries(productos)
          .filter(([, p]) => p.estrellas || p.comentario?.trim())
          .map(([producto_id, p]) => ({ producto_id, estrellas: p.estrellas ?? null, comentario: p.comentario || '' }))
      });
      olvidarTokensDeEnlace(RUTA);
      setVista({ estado: 'enviada', texto: data.mensaje });
    } catch (error) {
      const datos = error.response?.data;
      if (error.response?.status === 429) {
        setAviso({ tipo: 'error', texto: 'Enviaste muchos intentos seguidos. Inténtalo de nuevo en un rato.' });
      } else if (error.response?.status === 400 && datos && typeof datos === 'object') {
        const { productos: deProductos, ...porCampo } = datos;
        setErrores({
          ...Object.fromEntries(Object.entries(porCampo).map(([campo, m]) => [campo, comoTexto(m)])),
          productos: deProductos && typeof deProductos === 'object' ? deProductos : {}
        });
        setAviso({ tipo: 'error', texto: 'Revisa los datos marcados.' });
      } else {
        setAviso({ tipo: 'error', texto: datos?.detail || 'No se pudo enviar tu reseña. Inténtalo de nuevo.' });
      }
    } finally {
      setEnviando(false);
    }
  };

  const describir = (campo, ayuda) => ({
    'aria-invalid': errores[campo] ? true : undefined,
    'aria-describedby': [ayuda, errores[campo] && `resena-${campo}-error`].filter(Boolean).join(' ') || undefined
  });
  const errorCampo = (campo) => errores[campo] && (
    <p id={`resena-${campo}-error`} role="alert" className="checkout-error-campo">{errores[campo]}</p>
  );

  return (
    <>
      <Header />
      <main tabIndex={-1} id="contenido" className="checkout-main">
        <div className="checkout-card resena">
          {vista.estado === 'formulario' && <span className="antetitulo">Pedido #{vista.pedido.orden_id}</span>}
          <h1 className="checkout-titulo">Cuéntanos qué te pareció</h1>

          {vista.estado === 'cargando' && <p className="texto-secundario">Cargando tu pedido...</p>}

          {vista.estado === 'error' && (
            <p className="checkout-aviso checkout-aviso--advertencia">
              {vista.texto} <Link to="/catalogo">Ver el catálogo</Link>
            </p>
          )}

          {vista.estado === 'enviada' && (
            <>
              <p ref={agradecimiento} tabIndex={-1} role="status" className="checkout-aviso checkout-aviso--exito">
                {vista.texto}
              </p>
              <Link to="/" className="boton boton-primario">Volver a la tienda</Link>
            </>
          )}

          {vista.estado === 'formulario' && (
            <>
              <p className="resena-intro texto-secundario">
                Tu opinión ayuda a otros clientes. {tienda} la revisará antes de publicarla.
              </p>

              {aviso && (
                <p role={aviso.tipo === 'error' ? 'alert' : 'status'}
                  className={`checkout-aviso checkout-aviso--${aviso.tipo}`}>
                  {aviso.texto}
                </p>
              )}

              <form onSubmit={enviar} noValidate className="resena-formulario">
                <fieldset className="checkout-grupo checkout-seccion">
                  <legend className="checkout-paso">La tienda</legend>
                  <EstrellasEntrada nombre="resena-tienda" leyenda={`¿Cómo calificarías a ${tienda}?`} requerido
                    valor={estrellas} error={errores.estrellas}
                    onChange={(valor) => { setEstrellas(valor); setErrores(a => ({ ...a, estrellas: undefined })); }} />
                  <div className="checkout-campo">
                    <label htmlFor="resena-comentario">Comentario (opcional)</label>
                    <textarea id="resena-comentario" rows={4} maxLength={LARGO_COMENTARIO} value={comentario}
                      placeholder="¿Cómo fue la atención, el envío, el empaque?"
                      onChange={(e) => setComentario(e.target.value)} {...describir('comentario')} />
                    {errorCampo('comentario')}
                  </div>
                </fieldset>

                {vista.pedido.productos.length > 0 && (
                  <fieldset className="checkout-grupo checkout-seccion">
                    <legend className="checkout-paso">Lo que compraste (opcional)</legend>
                    {vista.pedido.productos.map(({ producto_id: id, nombre: producto }) => {
                      const calificacion = productos[id] || {};
                      const error = errores.productos?.[id];
                      return (
                        <div key={id} className="resena-producto">
                          <EstrellasEntrada nombre={`resena-producto-${id}`} leyenda={producto}
                            valor={calificacion.estrellas ?? null} error={error}
                            onChange={(valor) => editarProducto(id, { estrellas: valor })}
                            alQuitar={() => editarProducto(id, { estrellas: null })} />
                          <div className="checkout-campo">
                            <label htmlFor={`resena-comentario-${id}`}>Comentario sobre {producto} (opcional)</label>
                            <textarea id={`resena-comentario-${id}`} rows={2} maxLength={LARGO_COMENTARIO}
                              value={calificacion.comentario || ''}
                              onChange={(e) => editarProducto(id, { comentario: e.target.value })} />
                          </div>
                        </div>
                      );
                    })}
                  </fieldset>
                )}

                <fieldset className="checkout-grupo checkout-seccion">
                  <legend className="checkout-paso">Cómo se verá</legend>
                  <div className="checkout-campo">
                    <label htmlFor="resena-nombre">Nombre a mostrar</label>
                    <input id="resena-nombre" type="text" autoComplete="off" maxLength={LARGO_NOMBRE} required
                      value={nombre} {...describir('nombre_publico', 'resena-nombre-ayuda')}
                      onChange={(e) => {
                        setNombre(e.target.value);
                        setErrores(a => ({ ...a, nombre_publico: undefined }));
                      }} />
                    <p id="resena-nombre-ayuda" className="checkout-ayuda">
                      Así aparecerá junto a tu reseña. Tu correo nunca se muestra.
                    </p>
                    {errorCampo('nombre_publico')}
                  </div>

                  {/* Consentimiento obligatorio, desmarcado por defecto */}
                  <label className="checkout-casilla resena-acepta">
                    <input type="checkbox" checked={acepta} required onChange={(e) => setAcepta(e.target.checked)}
                      {...describir('acepta_publicacion')} />
                    <span>Acepto que mi reseña y el nombre que elegí se publiquen en la tienda.</span>
                  </label>
                  {errorCampo('acepta_publicacion')}
                </fieldset>

                <button type="submit" className="boton boton-primario resena-enviar" disabled={!acepta || enviando}>
                  {enviando && <Spinner />}{enviando ? 'Enviando...' : 'Enviar reseña'}
                </button>
              </form>
            </>
          )}
        </div>
      </main>
    </>
  );
}
