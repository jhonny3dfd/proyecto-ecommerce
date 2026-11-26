import { useId, useState, useEffect, useRef } from 'react';
import './VariantSelector.css';
import Spinner from './carga/Spinner';

function VariantSelector({ producto, onAgregarAlCarrito }) {
  const botonAgregar = useRef(null);
  const aviso = useRef(null);
  const [atributosSeleccionados, setAtributosSeleccionados] = useState({});
  // { tipo: 'exito' | 'error', texto }
  const [mensaje, setMensaje] = useState(null);
  const [cantidad, setCantidad] = useState(1);
  const [agregando, setAgregando] = useState(false);
  // Si el foco estaba en "Agregar al carrito", vuelve a él (o al aviso) cuando termina la validación del stock
  const devolverFoco = useRef(false);
  // Prefijo único para los ids de los títulos de cada grupo de atributos
  const idBase = useId();

  // Sincroniza con el carrito local para descontar lo que el usuario ya agregó
  const [itemsCarrito, setItemsCarrito] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('carrito_local')) || [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    const sincronizarCarrito = () => {
      try {
        setItemsCarrito(JSON.parse(localStorage.getItem('carrito_local')) || []);
      } catch {
        setItemsCarrito([]);
      }
    };
    window.addEventListener('carritoActualizado', sincronizarCarrito);
    window.addEventListener('storage', sincronizarCarrito);
    return () => {
      window.removeEventListener('carritoActualizado', sincronizarCarrito);
      window.removeEventListener('storage', sincronizarCarrito);
    };
  }, []);

  // Mientras valida, el botón está deshabilitado y el navegador puede sacarle el foco. Se devuelve aquí, después
  // de que React lo vuelve a habilitar: un requestAnimationFrame podía correr antes y el foco se perdía
  useEffect(() => {
    if (agregando || !devolverFoco.current) return;
    devolverFoco.current = false;
    // Si el comprador ya movió el foco a otra parte, no se le quita
    if (document.activeElement !== document.body && document.activeElement !== botonAgregar.current) return;
    const destino = botonAgregar.current?.disabled ? aviso.current : botonAgregar.current;
    destino?.focus();
  }, [agregando]);

  const obtenerCantidadEnCarrito = (sku) => {
    if (!sku) return 0;
    const item = itemsCarrito.find(i => i.sku === sku);
    return item ? Number(item.cantidad) || 0 : 0;
  };

  // Reinicia la selección cuando cambia el producto (no cuando solo se actualiza su stock).
  // Se ajusta durante el render, como recomienda React, en vez de usar un efecto.
  const productoId = producto?.id;
  const [productoAnterior, setProductoAnterior] = useState(productoId);
  if (productoId !== productoAnterior) {
    setProductoAnterior(productoId);
    setAtributosSeleccionados({});
    setMensaje(null);
    setCantidad(1);
  }

  const error = (texto) => setMensaje({ tipo: 'error', texto });

  // Si todavía no se ha seleccionado un producto
  if (!producto) {
    return (
      <div>
        <p>No se ha seleccionado ningún producto.</p>
      </div>
    );
  }

  const variantes = producto.variantes || [];

  // Obtiene los nombres de los atributos
  const nombresAtributos = [
    ...new Set(
      variantes.flatMap((variante) =>
        Object.keys(variante.atributos_variables || {})
      )
    ),
  ];

  const obtenerValores = (atributo) => {
    return [
      ...new Set(
        variantes
          .map((variante) => variante.atributos_variables?.[atributo])
          .filter((valor) => valor !== undefined && valor !== null)
      ),
    ];
  };

  const encontrarVariante = (atributos) => {
    if (variantes.length === 0) {
      return null;
    }

    // Una única opción sin atributos no requiere una selección del comprador.
    if (nombresAtributos.length === 0) {
      return variantes.length === 1 ? variantes[0] : null;
    }

    const todosSeleccionados = nombresAtributos.every(
      (atributo) => atributos[atributo] !== undefined
    );

    if (!todosSeleccionados) {
      return null;
    }

    return (
      variantes.find((variante) =>
        nombresAtributos.every(
          (atributo) =>
            variante.atributos_variables?.[atributo] === atributos[atributo]
        )
      ) || null
    );
  };

  const seleccionarAtributo = (atributo, valor) => {
    const nuevosAtributos = {
      ...atributosSeleccionados,
      [atributo]: valor,
    };

    setAtributosSeleccionados(nuevosAtributos);
    setCantidad(1);

    const variante = encontrarVariante(nuevosAtributos);
    if (!variante) {
      setMensaje(null);
      return;
    }

    const totalStock = Number(variante.stock) || 0;
    const enCarro = obtenerCantidadEnCarrito(variante.sku);
    const disp = Math.max(0, totalStock - enCarro);

    if (totalStock === 0) {
      error('Esta variante se encuentra agotada.');
      return;
    }

    if (disp === 0) {
      error(`Esta opción está agotada: ya tienes las ${totalStock} unidad(es) en tu carrito.`);
      return;
    }

    setMensaje(null);
  };

  const varianteSeleccionada = encontrarVariante(atributosSeleccionados);
  const stockTotal = varianteSeleccionada ? Number(varianteSeleccionada.stock) || 0 : 0;
  const enCarrito = varianteSeleccionada ? obtenerCantidadEnCarrito(varianteSeleccionada.sku) : 0;
  const stockDisponibleParaAgregar = Math.max(0, stockTotal - enCarrito);

  const tieneOferta = Boolean(
    varianteSeleccionada?.precio_oferta != null &&
    Number(varianteSeleccionada.precio_oferta) > 0 &&
    Number(varianteSeleccionada.precio_oferta) < Number(varianteSeleccionada.precio)
  );

  const sinStock = !varianteSeleccionada || stockTotal === 0 || stockDisponibleParaAgregar === 0;

  const agregarAlCarrito = async () => {
    if (!varianteSeleccionada) {
      error('Selecciona una variante primero.');
      return;
    }

    if (stockTotal === 0) {
      error('Esta variante se encuentra agotada.');
      return;
    }

    if (stockDisponibleParaAgregar <= 0) {
      error(`Ya tienes todas las unidades disponibles (${stockTotal}) en tu carrito.`);
      return;
    }

    if (!Number.isInteger(cantidad) || cantidad < 1) {
      error('La cantidad debe ser al menos 1.');
      return;
    }

    if (cantidad > stockDisponibleParaAgregar) {
      error(`Solo puedes agregar hasta ${stockDisponibleParaAgregar} unidad(es) más.`);
      return;
    }

    // Ejecutamos la función que nos pasaron desde DetalleProducto; el servidor confirma el stock
    if (onAgregarAlCarrito) {
      devolverFoco.current = document.activeElement === botonAgregar.current;
      setAgregando(true);
      setMensaje(null);
      const resultado = await onAgregarAlCarrito(varianteSeleccionada, cantidad);
      setAgregando(false);
      setMensaje({ tipo: resultado.ok ? 'exito' : 'error', texto: resultado.mensaje });
      if (resultado.ok) {
        setCantidad(1);
      }
    }
  };

  if (variantes.length === 0) {
    return (
      <div>
        <p>Este producto no tiene variantes disponibles.</p>
      </div>
    );
  }

  const formatear = (valor) => `$${Number(valor).toLocaleString('es-CL')}`;

  return (
    <div className="selector-variantes">
      {nombresAtributos.map((atributo, indice) => (
        <div key={atributo} className="selector-variantes-atributo">
          <h3 id={`${idBase}-atributo-${indice}`} className="selector-variantes-titulo">
            {atributo.replaceAll('_', ' ')}
            {atributosSeleccionados[atributo] !== undefined && (
              <span className="selector-variantes-elegido">: {String(atributosSeleccionados[atributo])}</span>
            )}
          </h3>

          <div role="group" aria-labelledby={`${idBase}-atributo-${indice}`} className="selector-variantes-opciones">
            {obtenerValores(atributo).map((valor) => {
              const seleccionado = atributosSeleccionados[atributo] === valor;
              // Una opción se marca agotada si la combinación no tiene stock o ya está toda en el carrito
              const tentativa = encontrarVariante({ ...atributosSeleccionados, [atributo]: valor });
              const tentStock = tentativa ? Number(tentativa.stock) || 0 : null;
              const tentEnCarrito = tentativa ? obtenerCantidadEnCarrito(tentativa.sku) : 0;
              const tentAgotada = tentativa && (tentStock === 0 || tentStock - tentEnCarrito <= 0);

              return (
                <button
                  key={valor}
                  type="button"
                  aria-pressed={seleccionado}
                  onClick={() => seleccionarAtributo(atributo, valor)}
                  className={`selector-variantes-opcion${tentAgotada ? ' selector-variantes-opcion--agotada' : ''}`}
                  title={tentAgotada ? 'Opción sin stock disponible' : ''}
                >
                  {valor}{tentAgotada && <span className="selector-variantes-opcion-nota"> (Agotado)</span>}
                </button>
              );
            })}
          </div>
        </div>
      ))}

      {varianteSeleccionada && (
        <div className="selector-variantes-resumen">
          <p className="selector-variantes-precio">
            <span>{formatear(tieneOferta ? varianteSeleccionada.precio_oferta : varianteSeleccionada.precio)}</span>
            {tieneOferta && (
              <del className="detalle-precio-anterior">
                <span className="visualmente-oculto">Precio anterior: </span>{formatear(varianteSeleccionada.precio)}
              </del>
            )}
          </p>

          <p className={stockDisponibleParaAgregar > 0 ? 'texto-secundario' : 'selector-variantes-agotado'}>
            {stockTotal === 0
              ? 'Agotado'
              : stockDisponibleParaAgregar === 0
                ? `Agotado (ya tienes las ${stockTotal} unidades disponibles en tu carrito)`
                : `Stock disponible: ${stockDisponibleParaAgregar}${enCarrito > 0 ? ` (${enCarrito} en tu carrito)` : ''}`}
          </p>

          <p className="selector-variantes-sku">SKU: {varianteSeleccionada.sku}</p>

          {/* La cantidad no puede pasar del stock que queda después de lo que ya está en el carrito */}
          {stockDisponibleParaAgregar > 0 && (
            <div className="selector-variantes-cantidad">
              <label htmlFor={`${idBase}-cantidad`}>Cantidad</label>
              <input
                type="number"
                id={`${idBase}-cantidad`}
                min="1"
                max={stockDisponibleParaAgregar}
                value={cantidad}
                onChange={(e) => setCantidad(Math.min(stockDisponibleParaAgregar, Math.max(1, Number(e.target.value))))}
              />
            </div>
          )}
        </div>
      )}

      <button
        ref={botonAgregar}
        type="button"
        onClick={agregarAlCarrito}
        disabled={sinStock || agregando}
        className="boton boton-primario selector-variantes-agregar"
      >
        {agregando && <Spinner />}
        {/* En su propio elemento: con la página traducida por el navegador, React cambia el texto entero */}
        <span>
          {agregando
            ? 'Verificando stock...'
            : stockTotal === 0
              ? 'Agotado'
              : stockDisponibleParaAgregar === 0
                ? 'Agotado (en tu carrito)'
                : 'Agregar al carrito'}
        </span>
      </button>

      {mensaje && (
        <p
          ref={aviso} tabIndex={-1}
          role={mensaje.tipo === 'error' ? 'alert' : 'status'}
          className={`selector-variantes-mensaje selector-variantes-mensaje--${mensaje.tipo}`}
        >
          {mensaje.texto}
        </p>
      )}
    </div>
  );
}

export default VariantSelector;
