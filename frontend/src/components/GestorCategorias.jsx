import { useEffect, useRef, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoLista } from './carga/EsqueletosPanel';
import Spinner from './carga/Spinner';

// Renombrar o unir categorías (RF-03.2). Una categoría es el texto de cada producto: aquí se cambia en todos de una
// vez. Si el nombre nuevo es el de otra (sin distinguir mayúsculas), las dos quedan unidas; así también se quita una.
// Las reglas viven en ecommerce/domain/categorias.py; esto solo anticipa qué va a pasar
const LARGO_NOMBRE = 100;
const limpiar = (texto) => String(texto || '').split(/\s+/).filter(Boolean).join(' ');
const clave = (texto) => limpiar(texto).toLocaleLowerCase('es');
const productosTexto = (n) => (n === 1 ? '1 producto' : `${n} productos`);

export default function GestorCategorias({ alCambiar }) {
  const [categorias, setCategorias] = useState(null);
  const [editando, setEditando] = useState(null);
  const [nombre, setNombre] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState(null);
  const [error, setError] = useState('');
  const botones = useRef({});
  const campo = useRef(null);

  useEffect(() => {
    clienteAxios.get('catalogo/categorias/')
      .then(({ data }) => setCategorias(data.categorias || []))
      .catch(() => {
        setCategorias([]);
        setAviso({ tipo: 'error', texto: 'No se pudieron cargar las categorías. Vuelve a abrir Configuración.' });
      });
  }, []);

  useEffect(() => {
    if (editando) campo.current?.focus();
  }, [editando]);

  const abrir = (categoria) => {
    setEditando(categoria.nombre);
    setNombre(categoria.nombre);
    setError('');
    setAviso(null);
  };

  const cerrar = (enfocar) => {
    const anterior = editando;
    setEditando(null);
    setError('');
    requestAnimationFrame(() => botones.current[enfocar || anterior]?.focus());
  };

  // Qué va a pasar con lo escrito, como lo decide el servidor
  const vistaPrevia = (actual) => {
    const nuevo = limpiar(nombre);
    if (!nuevo) return { error: 'Escribe el nombre nuevo de la categoría.' };
    if (nuevo === actual.nombre) return { error: 'Escribe un nombre distinto al actual.' };
    const otra = categorias.find(c => c.nombre !== actual.nombre && clave(c.nombre) === clave(nuevo));
    if (otra) {
      return { une: otra, texto: `Se unirá con «${otra.nombre}» (${productosTexto(otra.productos)}): quedará una sola categoría con ${productosTexto(otra.productos + actual.productos)}.` };
    }
    return { texto: `${actual.productos === 1 ? 'Su producto pasará' : `Sus ${actual.productos} productos pasarán`} a «${nuevo}».` };
  };

  const guardar = async (e, actual) => {
    e.preventDefault();
    const previa = vistaPrevia(actual);
    if (previa.error) {
      setError(previa.error);
      return;
    }
    if (previa.une && !window.confirm(`¿Unir «${actual.nombre}» con «${previa.une.nombre}»? Después no se pueden separar de una vez: habría que cambiar los productos uno por uno.`)) return;
    setGuardando(true);
    setError('');
    try {
      const { data } = await clienteAxios.post('catalogo/categorias/renombrar/', { desde: actual.nombre, hacia: nombre });
      setCategorias(data.categorias || []);
      setAviso({ tipo: 'exito', texto: data.une
        ? `Uniste «${data.desde}» con «${data.hacia}»: ${productosTexto(data.productos)} cambiaron de categoría.`
        : `Renombraste «${data.desde}» a «${data.hacia}» en ${productosTexto(data.productos)}.` });
      alCambiar?.();
      cerrar(data.hacia);
    } catch (err) {
      setError(err.response?.data?.detail || 'No se pudo cambiar la categoría. Inténtalo de nuevo.');
    } finally {
      setGuardando(false);
    }
  };

  if (categorias === null) return <Cargando texto="Cargando categorías..."><EsqueletoLista /></Cargando>;

  return (
    <>
      <p className="texto-secundario admin-descripcion">
        Corrige el nombre de una categoría o junta dos en una. El cambio se hace en todos sus productos (también los
        borradores), en el orden del catálogo y en los planes de suscripción. Para quitar una categoría, únela con otra
        escribiendo el nombre de esa otra.
      </p>

      {aviso && (
        <p role={aviso.tipo === 'error' ? 'alert' : 'status'} className={`admin-aviso admin-aviso--${aviso.tipo}`}>
          {aviso.texto}
        </p>
      )}

      {categorias.length === 0 ? (
        <p className="texto-secundario">Todavía no hay categorías: se crean al guardar un producto.</p>
      ) : (
        <ul className="lista-sin-estilo categorias-lista">
          {categorias.map(categoria => {
            const abierta = editando === categoria.nombre;
            const previa = abierta ? vistaPrevia(categoria) : null;
            const idCampo = `categoria-nueva-${categorias.indexOf(categoria)}`;
            return (
              <li key={categoria.nombre} className="categorias-item">
                <div className="categorias-fila">
                  <span className="categorias-nombre">
                    <strong>{categoria.nombre}</strong>
                    <span className="texto-secundario">
                      {productosTexto(categoria.productos)}
                      {categoria.publicados !== categoria.productos && ` (${categoria.publicados} publicados)`}
                    </span>
                  </span>
                  {!abierta && (
                    <button type="button" className="boton boton-contorno" disabled={guardando || editando !== null}
                      ref={el => { botones.current[categoria.nombre] = el; }}
                      aria-label={`Renombrar o unir ${categoria.nombre}`} onClick={() => abrir(categoria)}>
                      Renombrar o unir
                    </button>
                  )}
                </div>
                {abierta && (
                  <form className="categorias-formulario" onSubmit={e => guardar(e, categoria)} noValidate
                    onKeyDown={e => { if (e.key === 'Escape' && !guardando) { e.preventDefault(); cerrar(); } }}>
                    <div className="admin-campo">
                      <label htmlFor={idCampo}>Nuevo nombre para «{categoria.nombre}»</label>
                      <input id={idCampo} ref={campo} type="text" maxLength={LARGO_NOMBRE} list="categorias-existentes"
                        value={nombre} onChange={e => { setNombre(e.target.value); setError(''); }}
                        aria-describedby={`${idCampo}-ayuda${error ? ` ${idCampo}-error` : ''}`}
                        aria-invalid={error ? true : undefined} />
                      <p id={`${idCampo}-ayuda`} className="admin-ayuda" aria-live="polite">
                        {previa.texto || 'Escribe el nombre nuevo, o el de otra categoría para unirlas.'}
                      </p>
                      {error && <p id={`${idCampo}-error`} className="admin-error-campo">{error}</p>}
                    </div>
                    <div className="publicacion-acciones">
                      <button type="submit" className="boton boton-primario" disabled={guardando}>
                        {guardando && <Spinner />}{guardando ? 'Guardando...' : previa.une ? 'Unir categorías' : 'Renombrar'}
                      </button>
                      <button type="button" className="boton boton-contorno" disabled={guardando} onClick={() => cerrar()}>
                        Cancelar
                      </button>
                    </div>
                  </form>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <datalist id="categorias-existentes">
        {categorias.filter(c => c.nombre !== editando).map(c => <option key={c.nombre} value={c.nombre} />)}
      </datalist>
    </>
  );
}
