import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import useCarrito from '../hooks/useCarrito';
import { guardarCarrito, validarCarrito } from './carrito';

const CarritoCompras = () => {
    const botonRef = useRef(null);
    const [isOpen, setIsOpen] = useState(false);
    const carritoRef = useRef(null);
    const itemsCarrito = useCarrito();
    const [aviso, setAviso] = useState('');
    const [tipoAviso, setTipoAviso] = useState('status');
    const [actualizando, setActualizando] = useState(false);

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (carritoRef.current && !carritoRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);

        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, []);

    const mostrarAviso = (mensaje, tipo = 'status') => {
        setAviso(mensaje);
        setTipoAviso(tipo);
    };

    const cambiarCantidad = async (item, incremento) => {
        if (actualizando) return;

        const cantidadNueva = Number(item.cantidad) + incremento;
        if (cantidadNueva < 1) return;

        if (incremento < 0) {
            const nuevoCarrito = itemsCarrito.map(actual =>
                actual.id === item.id && actual.sku === item.sku
                    ? { ...actual, cantidad: cantidadNueva }
                    : actual
            );

            await guardarCarrito(nuevoCarrito);
            mostrarAviso('Cantidad actualizada.');
            return;
        }

        setActualizando(true);
        setAviso('');

        try {
            const candidato = itemsCarrito.map(actual =>
                actual.id === item.id && actual.sku === item.sku
                    ? { ...actual, cantidad: cantidadNueva }
                    : actual
            );

            const revision = await validarCarrito(candidato);
            const revisada = revision.items?.find(
                linea =>
                    linea.producto_mongo_id === item.id &&
                    linea.variante_sku === item.sku
            );

            if (!revisada) {
                mostrarAviso('No pudimos comprobar el stock. Inténtalo nuevamente.', 'alert');
                return;
            }

            if (revisada.problema || revisada.disponible < cantidadNueva) {
                mostrarAviso(
                    revisada.problema === 'STOCK_INSUFICIENTE'
                        ? `Solo quedan ${revisada.disponible} unidades.`
                        : revisada.mensaje || 'No se pudo aumentar la cantidad.',
                    'alert'
                );
                return;
            }

            const carritoNuevo = candidato.map(actual =>
                actual.id === item.id && actual.sku === item.sku
                    ? { ...actual, precio: revisada.precio ?? actual.precio }
                    : actual
            );

            await guardarCarrito(carritoNuevo);
            mostrarAviso('Cantidad actualizada.');
        } catch (error) {
            console.error('Error al actualizar el carrito:', error);
            mostrarAviso('No pudimos comprobar el stock. Inténtalo nuevamente.', 'alert');
        } finally {
            setActualizando(false);
        }
    };

    const quitarProducto = async (item) => {
        if (actualizando) return;

        const nuevoCarrito = itemsCarrito.filter(
            actual => !(actual.id === item.id && actual.sku === item.sku)
        );

        await guardarCarrito(nuevoCarrito);
        mostrarAviso('Producto quitado del carrito.');
    };

    const total = itemsCarrito.reduce((acc, item) => acc + (item.precio * item.cantidad), 0);
    const cantidadTotal = itemsCarrito.reduce((acc, item) => acc + item.cantidad, 0);

    return (
        // Se cierra si el foco pasa a algo fuera del carrito (ej. con Tab). Un blur sin destino no lo cierra: pasa al
        // deshabilitarse o desaparecer el botón enfocado, y los clics fuera ya los atiende handleClickOutside
        <div className="carrito-compras" ref={carritoRef} onBlur={event => { if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget)) setIsOpen(false); }} onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); setIsOpen(false); botonRef.current?.focus(); } }}>
            <button
                ref={botonRef}
                type="button"
                className="header-icono"
                onClick={() => setIsOpen(!isOpen)}
                aria-label={`Carrito de compras, ${cantidadTotal} ${cantidadTotal === 1 ? 'producto' : 'productos'}`}
                aria-expanded={isOpen}
            >
                {/* Bolsa de compras de trazo fino, como el resto de los íconos del header */}
                <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                    strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M6 7h12l-1 13H7L6 7Z" />
                    <path d="M9 7a3 3 0 0 1 6 0" />
                </svg>

                {cantidadTotal > 0 && (
                    <span aria-hidden="true" className="header-icono-contador">{cantidadTotal}</span>
                )}
            </button>

            {isOpen && (
                <div className="carrito-panel panel-header">
                    <div className="panel-header-encabezado">
                        <h3>Mi Carrito</h3>
                    </div>

                    <div className="carrito-panel-lista">
                        {aviso && (
                            <p role={tipoAviso} className={`carrito-aviso${tipoAviso === 'alert' ? ' carrito-aviso--error' : ''}`}>
                                {aviso}
                            </p>
                        )}

                        {itemsCarrito.length > 0 ? (
                            itemsCarrito.map(item => (
                                <div key={`${item.id}-${item.sku}`} className="carrito-item">
                                    <p className="carrito-item-nombre">{item.nombre}</p>

                                    <p className="carrito-item-precio">
                                        {/* Un solo texto: con la página traducida, React lo reemplaza entero */}
                                        {`$${(Number(item.precio) * item.cantidad).toLocaleString('es-CL')}`}
                                    </p>

                                    <div className="carrito-item-acciones">
                                        <div className="carrito-cantidad">
                                            <button
                                                type="button"
                                                onClick={() => cambiarCantidad(item, -1)}
                                                // aria-disabled y no disabled: el botón conserva el foco (con disabled
                                                // el foco se perdía al apretarlo); cambiarCantidad ignora el clic
                                                aria-disabled={item.cantidad <= 1 || actualizando}
                                                aria-label={`Disminuir cantidad de ${item.nombre}`}
                                            >
                                                −
                                            </button>

                                            <span aria-label={`Cantidad: ${item.cantidad}`}>
                                                {item.cantidad}
                                            </span>

                                            <button
                                                type="button"
                                                onClick={() => cambiarCantidad(item, 1)}
                                                aria-disabled={actualizando}
                                                aria-label={`Aumentar cantidad de ${item.nombre}`}
                                            >
                                                +
                                            </button>
                                        </div>

                                        <button
                                            type="button"
                                            className="carrito-quitar"
                                            onClick={() => quitarProducto(item)}
                                            aria-disabled={actualizando}
                                            aria-label={`Quitar ${item.nombre} del carrito`}
                                        >
                                            Quitar
                                        </button>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="carrito-vacio">
                                <p>Tu carrito está vacío</p>
                                <Link to="/catalogo" className="enlace-flecha" onClick={() => setIsOpen(false)}>
                                    Ver catálogo <span aria-hidden="true">→</span>
                                </Link>
                            </div>
                        )}
                    </div>

                    {itemsCarrito.length > 0 && (
                        <div className="carrito-panel-pie">
                            <div className="carrito-total">
                                <span>Total:</span>
                                <span>{`$${total.toLocaleString('es-CL')}`}</span>
                            </div>
                            <Link to="/checkout" onClick={() => setIsOpen(false)} className="boton boton-primario carrito-pagar">
                                Ir a Pagar
                            </Link>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default CarritoCompras;
