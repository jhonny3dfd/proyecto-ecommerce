import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import clienteAxios from '../components/auth/axiosConfig';
import DatosEmpresa from '../components/DatosEmpresa';
import Header from '../components/header/header';
import useConfiguracionTienda from '../hooks/useConfiguracionTienda';
import { EMPRESA_VACIA, normalizarRut, validarDatosEmpresa } from '../utils/empresa';
import { soloCaracteresDeTelefono } from '../utils/telefono';
import '../components/Checkout.css';
import '../components/FotosCotizacion.css';
import './Cotizacion.css';
import Spinner from '../components/carga/Spinner';

const FORMULARIO_VACIO = {
  nombre: '', correo: '', telefono: '', producto_id: '', descripcion: '', cantidad: '1',
  personalizacion: '', fecha_requerida: ''
};

// Fecha de hoy en la hora del navegador (AAAA-MM-DD), para no ofrecer fechas pasadas
const hoy = () => {
  const ahora = new Date();
  return new Date(ahora.getTime() - ahora.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

// El backend responde { campo: mensaje | [mensajes] } y los de la empresa anidados en 'empresa'. Los de las fotos
// vienen por foto ({ 0: [mensaje] }): se juntan en un solo texto
const comoTexto = (mensajes) => (mensajes && typeof mensajes === 'object' && !Array.isArray(mensajes)
  ? Object.values(mensajes).map(comoTexto).join(' ')
  : [].concat(mensajes).join(' '));

// Fotos de la idea: las mismas reglas que el servidor (domain/cotizaciones.py y el control de imágenes del catálogo)
const MAX_FOTOS = 3;
const FORMATOS_FOTO = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_BYTES_FOTO = 5 * 1024 * 1024;

export default function Cotizacion() {
  const configuracion = useConfiguracionTienda();
  const [parametros] = useSearchParams();
  const [productos, setProductos] = useState([]);
  const [formulario, setFormulario] = useState({ ...FORMULARIO_VACIO, producto_id: parametros.get('producto') || '' });
  const [comoEmpresa, setComoEmpresa] = useState(false);
  const [empresa, setEmpresa] = useState(EMPRESA_VACIA);
  const [aceptaPrivacidad, setAceptaPrivacidad] = useState(false);
  // Campo trampa: las personas no lo ven; si llega lleno, lo completó un bot
  const [sitioWeb, setSitioWeb] = useState('');
  const [errores, setErrores] = useState({});
  const [erroresEmpresa, setErroresEmpresa] = useState({});
  const [aviso, setAviso] = useState(null);
  const [enviando, setEnviando] = useState(false);
  // { archivo, vista }: la vista previa es un object URL que se libera al quitar la foto o salir de la página
  const [fotos, setFotos] = useState([]);

  const fotosActuales = useRef(fotos);
  useEffect(() => { fotosActuales.current = fotos; }, [fotos]);
  // Al salir de la página se liberan las que queden
  useEffect(() => () => fotosActuales.current.forEach(foto => URL.revokeObjectURL(foto.vista)), []);

  const agregarFotos = (e) => {
    const elegidas = Array.from(e.target.files || []);
    e.target.value = '';
    const libres = MAX_FOTOS - fotos.length;
    const invalida = elegidas.find(archivo => !FORMATOS_FOTO.includes(archivo.type) || archivo.size > MAX_BYTES_FOTO);
    if (invalida) {
      setErrores(actual => ({ ...actual, fotos: `"${invalida.name}" no sirve: usa JPG, PNG o WebP de hasta 5 MB.` }));
      return;
    }
    if (elegidas.length > libres) {
      setErrores(actual => ({ ...actual, fotos: `Puedes adjuntar hasta ${MAX_FOTOS} fotos.` }));
      return;
    }
    setErrores(actual => ({ ...actual, fotos: undefined }));
    setFotos(actual => [...actual, ...elegidas.map(archivo => ({ archivo, vista: URL.createObjectURL(archivo) }))]);
  };

  const quitarFoto = (indice) => {
    URL.revokeObjectURL(fotos[indice].vista);
    setFotos(actual => actual.filter((_, i) => i !== indice));
    setErrores(actual => ({ ...actual, fotos: undefined }));
  };

  useEffect(() => {
    // Sin `todos` el catálogo llega paginado; el selector necesita la lista completa
    clienteAxios.get('catalogo/productos/?todos=true')
      // Con sesión de admin también llegan los borradores: solo se cotiza lo publicado
      .then(({ data }) => setProductos((data || []).filter(p => p.activo !== false && p.publicado !== false)))
      .catch(() => setProductos([]));
  }, []);

  const editar = (campo, valor) => {
    setFormulario(actual => ({ ...actual, [campo]: valor }));
    setErrores(actual => ({ ...actual, [campo]: undefined }));
  };

  const editarEmpresa = (campo, valor) => {
    setEmpresa(actual => ({ ...actual, [campo]: valor }));
    setErroresEmpresa(actual => ({ ...actual, [campo]: undefined }));
  };

  const enviar = async (e) => {
    e.preventDefault();
    setAviso(null);
    if (comoEmpresa) {
      const faltantes = validarDatosEmpresa(empresa);
      if (Object.keys(faltantes).length > 0) {
        setErroresEmpresa(faltantes);
        setAviso({ tipo: 'error', texto: 'Revisa los datos de la empresa para la factura.' });
        return;
      }
    }
    setEnviando(true);
    try {
      const solicitud = {
        ...formulario,
        cantidad: Number(formulario.cantidad),
        fecha_requerida: formulario.fecha_requerida || null,
        como_empresa: comoEmpresa,
        empresa: comoEmpresa ? { ...empresa, rut: normalizarRut(empresa.rut) } : null,
        acepta_privacidad: aceptaPrivacidad,
        sitio_web: sitioWeb
      };
      // Con fotos va como multipart: los datos en "datos" (JSON) y cada foto en "fotos"
      let cuerpo = solicitud;
      if (fotos.length > 0) {
        cuerpo = new FormData();
        cuerpo.append('datos', JSON.stringify(solicitud));
        fotos.forEach(foto => cuerpo.append('fotos', foto.archivo));
      }
      const { data } = await clienteAxios.post('ventas/cotizaciones/', cuerpo);
      setFormulario(FORMULARIO_VACIO);
      fotos.forEach(foto => URL.revokeObjectURL(foto.vista));
      setFotos([]);
      setEmpresa(EMPRESA_VACIA);
      setComoEmpresa(false);
      setAceptaPrivacidad(false);
      setErrores({});
      setAviso({ tipo: 'exito', texto: data.mensaje });
    } catch (error) {
      const datos = error.response?.data;
      if (error.response?.status === 429) {
        setAviso({ tipo: 'error', texto: 'Enviaste muchas solicitudes seguidas. Inténtalo de nuevo en un rato.' });
      } else if (datos && typeof datos === 'object' && !datos.detail) {
        const { empresa: deEmpresa, ...porCampo } = datos;
        setErrores(Object.fromEntries(Object.entries(porCampo).map(([campo, m]) => [campo, comoTexto(m)])));
        if (deEmpresa && typeof deEmpresa === 'object') {
          setErroresEmpresa(Object.fromEntries(Object.entries(deEmpresa).map(([campo, m]) => [campo, comoTexto(m)])));
        }
        setAviso({ tipo: 'error', texto: 'Revisa los datos marcados.' });
      } else {
        setAviso({ tipo: 'error', texto: datos?.detail || 'No se pudo enviar tu solicitud. Inténtalo de nuevo.' });
      }
    } finally {
      setEnviando(false);
    }
  };

  // Asocia el error del backend con su campo (aria-describedby)
  const describir = (campo, ayuda) => ({
    'aria-invalid': errores[campo] ? true : undefined,
    'aria-describedby': [ayuda, errores[campo] && `cotizacion-${campo}-error`].filter(Boolean).join(' ') || undefined
  });
  const errorCampo = (campo) => errores[campo] && (
    <p id={`cotizacion-${campo}-error`} role="alert" className="checkout-error-campo">{errores[campo]}</p>
  );

  const activas = configuracion?.cotizaciones_activas;

  return (
    <>
      <Header />
      <main className="checkout-main">
        <div className="checkout-card cotizacion">
          <span className="antetitulo">Encargos y pedidos especiales</span>
          <h1 className="checkout-titulo">Cotizar</h1>

          {configuracion && !activas ? (
            <p className="checkout-aviso checkout-aviso--advertencia">
              Esta tienda no está recibiendo cotizaciones por ahora. <Link to="/catalogo">Ver el catálogo</Link>
            </p>
          ) : configuracion && (
            <>
              <p className="cotizacion-intro texto-secundario">
                ¿Necesitas un producto personalizado, hecho a pedido o en cantidad, para ti o para tu empresa?
                Cuéntanos qué buscas y te responderemos con el precio y el plazo.
              </p>

              {aviso && (
                <p role={aviso.tipo === 'error' ? 'alert' : 'status'}
                  className={`checkout-aviso checkout-aviso--${aviso.tipo}`}>
                  {aviso.texto}
                </p>
              )}

              <form onSubmit={enviar} className="cotizacion-formulario">
                <fieldset className="checkout-grupo checkout-seccion">
                  <legend className="checkout-paso">¿Qué necesitas?</legend>
                  <div className="checkout-campo">
                    <label htmlFor="cotizacion-producto">Producto</label>
                    <select id="cotizacion-producto" value={formulario.producto_id}
                      onChange={(e) => editar('producto_id', e.target.value)} {...describir('producto_id')}>
                      <option value="">Otro: lo describo abajo</option>
                      {formulario.producto_id && !productos.some(p => p.id === formulario.producto_id) && (
                        <option value={formulario.producto_id}>Producto elegido en el catálogo</option>
                      )}
                      {productos.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                    </select>
                    {errorCampo('producto_id')}
                  </div>
                  <div className="checkout-campo">
                    <label htmlFor="cotizacion-descripcion">
                      {formulario.producto_id ? 'Detalles (opcional)' : 'Describe lo que necesitas'}
                    </label>
                    <textarea id="cotizacion-descripcion" rows={3} maxLength={2000} value={formulario.descripcion}
                      required={!formulario.producto_id} onChange={(e) => editar('descripcion', e.target.value)}
                      {...describir('descripcion')} />
                    {errorCampo('descripcion')}
                  </div>
                  <div className="checkout-fila">
                    <div className="checkout-campo">
                      <label htmlFor="cotizacion-cantidad">Cantidad</label>
                      <input id="cotizacion-cantidad" type="number" inputMode="numeric" min={1} max={100000} step={1}
                        value={formulario.cantidad} required onChange={(e) => editar('cantidad', e.target.value)}
                        {...describir('cantidad')} />
                      {errorCampo('cantidad')}
                    </div>
                    <div className="checkout-campo">
                      <label htmlFor="cotizacion-fecha">¿Para cuándo lo necesitas? (opcional)</label>
                      <input id="cotizacion-fecha" type="date" min={hoy()} value={formulario.fecha_requerida}
                        onChange={(e) => editar('fecha_requerida', e.target.value)} {...describir('fecha_requerida')} />
                      {errorCampo('fecha_requerida')}
                    </div>
                  </div>
                  <div className="checkout-campo">
                    <label htmlFor="cotizacion-personalizacion">Personalización (opcional)</label>
                    <textarea id="cotizacion-personalizacion" rows={3} maxLength={2000}
                      value={formulario.personalizacion} onChange={(e) => editar('personalizacion', e.target.value)}
                      placeholder="Ej: con el nombre Sofía, en letras doradas"
                      {...describir('personalizacion', 'cotizacion-personalizacion-ayuda')} />
                    <p id="cotizacion-personalizacion-ayuda" className="checkout-ayuda">
                      Nombres, colores, logo, texto o lo que quieras agregar. Si tienes una foto o un dibujo de tu idea,
                      adjúntalo abajo.
                    </p>
                    {errorCampo('personalizacion')}
                  </div>

                  <div className="checkout-campo">
                    <label htmlFor="cotizacion-fotos">Fotos de tu idea (opcional)</label>
                    {fotos.length > 0 && (
                      <ul className="cotizacion-fotos" aria-label="Fotos adjuntas">
                        {fotos.map((foto, indice) => (
                          <li key={foto.vista}>
                            <img src={foto.vista} alt={`Foto ${indice + 1}: ${foto.archivo.name}`} />
                            <button type="button" className="boton-edicion" onClick={() => quitarFoto(indice)}
                              aria-label={`Quitar la foto ${indice + 1}`}>
                              Quitar
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                    {fotos.length < MAX_FOTOS && (
                      <input id="cotizacion-fotos" type="file" accept={FORMATOS_FOTO.join(',')} multiple
                        onChange={agregarFotos} {...describir('fotos', 'cotizacion-fotos-ayuda')} />
                    )}
                    <p id="cotizacion-fotos-ayuda" className="checkout-ayuda">
                      Hasta {MAX_FOTOS} fotos JPG, PNG o WebP de 5 MB cada una. Solo las ve la tienda.
                    </p>
                    {errorCampo('fotos')}
                  </div>
                </fieldset>

                <fieldset className="checkout-grupo checkout-seccion">
                  <legend className="checkout-paso">Tus datos de contacto</legend>
                  <div className="checkout-campo">
                    <label htmlFor="cotizacion-nombre">Nombre</label>
                    <input id="cotizacion-nombre" type="text" autoComplete="name" maxLength={120} required
                      value={formulario.nombre} onChange={(e) => editar('nombre', e.target.value)} {...describir('nombre')} />
                    {errorCampo('nombre')}
                  </div>
                  <div className="checkout-fila">
                    <div className="checkout-campo">
                      <label htmlFor="cotizacion-correo">Correo</label>
                      <input id="cotizacion-correo" type="email" autoComplete="email" required value={formulario.correo}
                        onChange={(e) => editar('correo', e.target.value)} {...describir('correo')} />
                      {errorCampo('correo')}
                    </div>
                    <div className="checkout-campo">
                      <label htmlFor="cotizacion-telefono">Teléfono</label>
                      <input id="cotizacion-telefono" type="tel" inputMode="tel" autoComplete="tel" maxLength={30} required
                        placeholder="+56 9 1234 5678" value={formulario.telefono}
                        onChange={(e) => editar('telefono', soloCaracteresDeTelefono(e.target.value))} {...describir('telefono')} />
                      {errorCampo('telefono')}
                    </div>
                  </div>

                  <label className="checkout-casilla">
                    <input type="checkbox" checked={comoEmpresa}
                      onChange={(e) => { setComoEmpresa(e.target.checked); setErroresEmpresa({}); }} />
                    Cotizo para una empresa y necesito factura
                  </label>
                  {comoEmpresa && (
                    <DatosEmpresa id="cotizacion-empresa" datos={empresa} errores={erroresEmpresa} onChange={editarEmpresa} />
                  )}
                </fieldset>

                {/* Campo trampa contra el spam: fuera de la vista y del teclado */}
                <div className="cotizacion-trampa" aria-hidden="true">
                  <label htmlFor="cotizacion-sitio">No completes este campo</label>
                  <input id="cotizacion-sitio" type="text" tabIndex={-1} autoComplete="off" value={sitioWeb}
                    onChange={(e) => setSitioWeb(e.target.value)} />
                </div>

                {/* Consentimiento obligatorio, desmarcado por defecto */}
                <label className="checkout-casilla cotizacion-privacidad">
                  <input type="checkbox" checked={aceptaPrivacidad} required
                    onChange={(e) => setAceptaPrivacidad(e.target.checked)} {...describir('acepta_privacidad')} />
                  <span>
                    Acepto que la tienda use mis datos para responder esta solicitud, según su{' '}
                    <a href="/legal/privacidad" target="_blank" rel="noopener noreferrer"
                      aria-label="Política de Privacidad (se abre en otra pestaña)">Política de Privacidad</a>.
                  </span>
                </label>
                {errorCampo('acepta_privacidad')}

                <button type="submit" className="boton boton-primario cotizacion-enviar"
                  disabled={!aceptaPrivacidad || enviando}>
                  {enviando && <Spinner />}{enviando ? 'Enviando...' : 'Enviar solicitud'}
                </button>
              </form>
            </>
          )}
        </div>
      </main>
    </>
  );
}
