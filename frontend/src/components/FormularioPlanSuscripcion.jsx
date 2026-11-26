import { useId, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import Spinner from './carga/Spinner';
import { descuentoSuscriptor, formatoPesos } from '../utils/suscripciones';

// Crear o editar un plan de suscripción (pedido de un cliente, opcional). Los límites son los de
// domain/suscripciones.py, que valida de verdad (DatosPlan.desde)
const LARGO_NOMBRE = 60;
const LARGO_DESCRIPCION = 300;
const MAX_BENEFICIOS = 10;
const LARGO_BENEFICIO = 120;
const FRECUENCIAS = [1, 2, 3, 4, 6, 8, 12];
const CAMPOS = ['nombre', 'descripcion', 'precio', 'frecuencia_semanas', 'unidades', 'beneficios', 'categorias',
  'productos', 'envio_gratis', 'envio_gratis_compras', 'descuento', 'activo'];

const formularioDe = (plan) => ({
  nombre: plan?.nombre || '',
  descripcion: plan?.descripcion || '',
  precio: plan?.precio ?? '',
  frecuencia_semanas: plan?.frecuencia_semanas ?? 4,
  unidades: plan?.unidades ?? 1,
  beneficios: (plan?.beneficios || []).join('\n'),
  categorias: plan?.categorias || [],
  productos: plan?.productos || [],
  envio_gratis: Boolean(plan?.envio_gratis),
  envio_gratis_compras: Boolean(plan?.envio_gratis_compras),
  descuento: plan?.descuento ?? 0,
  activo: plan ? Boolean(plan.activo) : true
});

// Un beneficio por línea, sin líneas vacías
const lineas = (texto) => texto.split('\n').map(linea => linea.trim()).filter(Boolean);

const paraElServidor = (formulario) => ({
  ...formulario,
  precio: formulario.precio === '' ? null : Number(formulario.precio),
  frecuencia_semanas: Number(formulario.frecuencia_semanas),
  unidades: formulario.unidades === '' ? null : Number(formulario.unidades),
  descuento: formulario.descuento === '' ? 0 : Number(formulario.descuento),
  beneficios: lineas(formulario.beneficios),
  // Sin envío gratis de la suscripción no hay envío gratis en las compras (el servidor lo exige)
  envio_gratis_compras: formulario.envio_gratis && formulario.envio_gratis_compras
});

// El backend responde { errores: { campo: mensaje } } o { detail }
const erroresDe = (error) => {
  const datos = error.response?.data;
  if (datos?.errores && typeof datos.errores === 'object') {
    const porCampo = Object.fromEntries(Object.entries(datos.errores)
      .filter(([campo]) => CAMPOS.includes(campo))
      .map(([campo, mensaje]) => [campo, [].concat(mensaje).join(' ')]));
    return { ...porCampo, general: 'Revisa los datos marcados.' };
  }
  return { general: datos?.detail || 'No se pudo guardar el plan. Inténtalo de nuevo.' };
};

export default function FormularioPlanSuscripcion({ plan, categorias, productos, alGuardar, alCancelar }) {
  const prefijo = useId();
  const [formulario, setFormulario] = useState(() => formularioDe(plan));
  const [errores, setErrores] = useState({});
  const [guardando, setGuardando] = useState(false);
  const [buscar, setBuscar] = useState('');

  const editar = (campo, valor) => {
    setFormulario(actual => ({ ...actual, [campo]: valor }));
    setErrores(actual => ({ ...actual, [campo]: undefined, general: undefined }));
  };

  const alternar = (campo, valor) => {
    const actual = formulario[campo];
    editar(campo, actual.includes(valor) ? actual.filter(v => v !== valor) : [...actual, valor]);
    // Elegir categorías o productos responde al mismo error ("elige al menos uno")
    setErrores(previos => ({ ...previos, categorias: undefined, productos: undefined }));
  };

  const guardar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setErrores({});
    try {
      const datos = paraElServidor(formulario);
      const { data } = plan
        ? await clienteAxios.put(`ventas/admin/suscripciones/planes/${plan.id}/`, datos)
        : await clienteAxios.post('ventas/admin/suscripciones/planes/', datos);
      alGuardar(data);
    } catch (error) {
      setErrores(erroresDe(error));
      setGuardando(false);
    }
  };

  const id = (campo) => `${prefijo}-${campo}`;
  const describir = (campo, ayuda) => {
    const ids = [ayuda && id(`${campo}-ayuda`), errores[campo] && id(`${campo}-error`)].filter(Boolean).join(' ');
    return { 'aria-describedby': ids || undefined, 'aria-invalid': errores[campo] ? true : undefined };
  };
  const errorCampo = (campo) => errores[campo]
    ? <p id={id(`${campo}-error`)} className="admin-error-campo">{errores[campo]}</p>
    : null;

  // Los productos elegidos que ya no están en el catálogo se muestran igual, para poder quitarlos
  const idsCatalogo = new Set(productos.map(p => p.id));
  const faltantes = formulario.productos.filter(pid => !idsCatalogo.has(pid))
    .map(pid => ({ id: pid, nombre: 'Producto que ya no está en el catálogo', categoria: '' }));
  const texto = buscar.trim().toLowerCase();
  const visibles = [...faltantes, ...productos].filter(p => !texto || formulario.productos.includes(p.id)
    || `${p.nombre} ${p.categoria}`.toLowerCase().includes(texto));
  const faltanCategorias = formulario.categorias.filter(c => !categorias.includes(c));

  const cantidadBeneficios = lineas(formulario.beneficios).length;
  const precio = Number(formulario.precio) || 0;
  const ejemploDescuento = descuentoSuscriptor(20000, formulario.descuento);

  return (
    <form onSubmit={guardar} className="admin-formulario plan-formulario" noValidate>
      <h5 className="plan-formulario-titulo">{plan ? `Editar "${plan.nombre}"` : 'Nuevo plan'}</h5>

      {errores.general && <p role="alert" className="admin-aviso admin-aviso--error">{errores.general}</p>}

      <div className="admin-campo">
        <label htmlFor={id('nombre')}>Nombre del plan</label>
        <input id={id('nombre')} type="text" required maxLength={LARGO_NOMBRE} value={formulario.nombre}
          onChange={e => editar('nombre', e.target.value)} placeholder="Ej. Café del mes"
          {...describir('nombre')} />
        {errorCampo('nombre')}
      </div>

      <div className="admin-campo">
        <label htmlFor={id('descripcion')}>Descripción (opcional)</label>
        <textarea id={id('descripcion')} rows={3} maxLength={LARGO_DESCRIPCION} value={formulario.descripcion}
          onChange={e => editar('descripcion', e.target.value)} {...describir('descripcion', true)} />
        <p id={id('descripcion-ayuda')} className="admin-ayuda">
          Se muestra bajo el nombre en la página de suscripciones. Hasta {LARGO_DESCRIPCION} caracteres.
        </p>
        {errorCampo('descripcion')}
      </div>

      <div className="admin-fila">
        <div className="admin-campo">
          <label htmlFor={id('precio')}>Precio por entrega ($)</label>
          <input id={id('precio')} type="number" inputMode="numeric" required min={1} step={1}
            value={formulario.precio} onChange={e => editar('precio', e.target.value)} placeholder="Ej. 15990"
            {...describir('precio', true)} />
          <p id={id('precio-ayuda')} className="admin-ayuda">
            Lo que paga el cliente en cada entrega, sin el despacho{precio > 0 ? ` (${formatoPesos(precio)})` : ''}.
          </p>
          {errorCampo('precio')}
        </div>
        <div className="admin-campo">
          <label htmlFor={id('frecuencia')}>Cada cuánto llega</label>
          <select id={id('frecuencia')} value={formulario.frecuencia_semanas}
            onChange={e => editar('frecuencia_semanas', e.target.value)} {...describir('frecuencia_semanas')}>
            {FRECUENCIAS.map(semanas => (
              <option key={semanas} value={semanas}>{semanas === 1 ? 'Cada semana' : `Cada ${semanas} semanas`}</option>
            ))}
          </select>
          {errorCampo('frecuencia_semanas')}
        </div>
        <div className="admin-campo">
          <label htmlFor={id('unidades')}>Unidades por entrega</label>
          <input id={id('unidades')} type="number" inputMode="numeric" required min={1} max={20} step={1}
            value={formulario.unidades} onChange={e => editar('unidades', e.target.value)}
            {...describir('unidades', true)} />
          <p id={id('unidades-ayuda')} className="admin-ayuda">Del producto que elija el cliente.</p>
          {errorCampo('unidades')}
        </div>
      </div>

      <fieldset className="admin-opciones plan-elegibles">
        <legend>Qué puede elegir el cliente</legend>
        <p className="admin-ayuda">
          Elige categorías completas (también entran los productos que agregues después a ellas), productos sueltos
          o ambos. El cliente elige uno al suscribirse y puede cambiarlo después.
        </p>

        <fieldset className="admin-opciones plan-elegibles-grupo" aria-describedby={errores.categorias ? id('categorias-error') : undefined}>
          <legend>Categorías</legend>
          {categorias.length === 0 && faltanCategorias.length === 0 && (
            <p className="texto-secundario">Todavía no hay categorías con productos.</p>
          )}
          <div className="plan-casillas">
            {[...categorias, ...faltanCategorias].map(categoria => (
              <label key={categoria} className="admin-casilla">
                <input type="checkbox" checked={formulario.categorias.includes(categoria)}
                  onChange={() => alternar('categorias', categoria)} />
                {categoria}{faltanCategorias.includes(categoria) ? ' (sin productos)' : ''}
              </label>
            ))}
          </div>
          {errorCampo('categorias')}
        </fieldset>

        <fieldset className="admin-opciones plan-elegibles-grupo" aria-describedby={errores.productos ? id('productos-error') : undefined}>
          <legend>Productos sueltos ({formulario.productos.length} elegidos)</legend>
          <div className="admin-campo">
            <label htmlFor={id('buscar')}>Buscar producto</label>
            <input id={id('buscar')} type="search" value={buscar} onChange={e => setBuscar(e.target.value)}
              placeholder="Nombre o categoría" />
          </div>
          <div className="plan-casillas plan-casillas--productos" role="group" aria-label="Productos del catálogo">
            {visibles.map(producto => (
              <label key={producto.id} className="admin-casilla">
                <input type="checkbox" checked={formulario.productos.includes(producto.id)}
                  onChange={() => alternar('productos', producto.id)} />
                <span>
                  {producto.nombre}
                  {producto.categoria && <span className="texto-secundario"> · {producto.categoria}</span>}
                </span>
              </label>
            ))}
            {visibles.length === 0 && <p className="texto-secundario">Ningún producto coincide con la búsqueda.</p>}
          </div>
          {errorCampo('productos')}
        </fieldset>
      </fieldset>

      <div className="admin-campo">
        <label htmlFor={id('beneficios')}>Beneficios (opcional, uno por línea)</label>
        <textarea id={id('beneficios')} rows={4} value={formulario.beneficios}
          onChange={e => editar('beneficios', e.target.value)}
          placeholder={'Café recién tostado\nGuía de preparación en cada entrega'}
          {...describir('beneficios', true)} />
        <p id={id('beneficios-ayuda')} className="admin-ayuda">
          Se muestran como lista en el plan. Hasta {MAX_BENEFICIOS}, de {LARGO_BENEFICIO} caracteres cada uno
          ({cantidadBeneficios} de {MAX_BENEFICIOS}). El descuento y el envío gratis se agregan solos.
        </p>
        {errorCampo('beneficios')}
      </div>

      <div className="admin-campo">
        <label htmlFor={id('descuento')}>Descuento en sus otras compras (%)</label>
        <input id={id('descuento')} type="number" inputMode="numeric" min={0} max={90} step={1}
          value={formulario.descuento} onChange={e => editar('descuento', e.target.value)}
          {...describir('descuento', true)} />
        <p id={id('descuento-ayuda')} className="admin-ayuda">
          Mientras la suscripción esté activa, en todo lo que compre en la tienda con su cuenta (después del código de
          descuento, si usa uno). 0 para no dar descuento.
          {ejemploDescuento > 0 && ` Ej.: en una compra de $20.000 ahorra ${formatoPesos(ejemploDescuento)}.`}
        </p>
        {errorCampo('descuento')}
      </div>

      <div>
        <label className="admin-casilla">
          <input type="checkbox" checked={formulario.envio_gratis}
            onChange={e => editar('envio_gratis', e.target.checked)} {...describir('envio_gratis', true)} />
          Envío gratis en las entregas de la suscripción
        </label>
        <p id={id('envio_gratis-ayuda')} className="admin-ayuda admin-ayuda--sangria">
          Sin marcar, cada entrega cobra el despacho cotizado a su dirección.
        </p>
        {errorCampo('envio_gratis')}
      </div>

      <div>
        <label className="admin-casilla">
          <input type="checkbox" checked={formulario.envio_gratis && formulario.envio_gratis_compras}
            disabled={!formulario.envio_gratis}
            onChange={e => editar('envio_gratis_compras', e.target.checked)} {...describir('envio_gratis_compras', true)} />
          Envío gratis también en todas sus otras compras
        </label>
        <p id={id('envio_gratis_compras-ayuda')} className="admin-ayuda admin-ayuda--sangria">
          Requiere el envío gratis de la suscripción. Vale mientras esté activa.
        </p>
        {errorCampo('envio_gratis_compras')}
      </div>

      <div>
        <label className="admin-casilla">
          <input type="checkbox" checked={formulario.activo} onChange={e => editar('activo', e.target.checked)}
            {...describir('activo', true)} />
          Plan disponible para nuevas suscripciones
        </label>
        <p id={id('activo-ayuda')} className="admin-ayuda admin-ayuda--sangria">
          Desmarcado, el plan no se muestra en la tienda; quienes ya están suscritos siguen igual.
        </p>
      </div>

      <div className="publicacion-acciones">
        <button type="submit" disabled={guardando} className="boton boton-primario">
          {guardando && <Spinner />}{guardando ? 'Guardando...' : plan ? 'Guardar cambios' : 'Crear plan'}
        </button>
        <button type="button" className="boton boton-contorno" onClick={alCancelar} disabled={guardando}>
          Cancelar
        </button>
      </div>
    </form>
  );
}
