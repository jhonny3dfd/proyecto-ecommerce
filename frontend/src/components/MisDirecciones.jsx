import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import clienteAxios from './auth/axiosConfig';
import { aplicarPaleta } from '../constants/palettes';
import Header from './header/header';
import './MisDirecciones.css';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoLista } from './carga/EsqueletosPanel';

const TEMA_PREDETERMINADO = 1;

const MisDirecciones = () => {
    const [direcciones, setDirecciones] = useState([]);
    const [cargando, setCargando] = useState(true);
    const [error, setError] = useState('');
    const [mensajeExito, setMensajeExito] = useState('');
    
    // Estados para el formulario de nueva dirección
    const [mostrandoFormulario, setMostrandoFormulario] = useState(false);
    const [listaComunas, setListaComunas] = useState([]);
    // Las comunas se piden una sola vez, al abrir la página
    const [cargandoComunas, setCargandoComunas] = useState(true);
    
    const [nuevaDireccion, setNuevaDireccion] = useState({
        calle: '',
        calle_numero: '',
        dpto_casa: '', // <- NUEVO CAMPO
        comuna: '',
        ciudad: '',
        region: '',
        es_predeterminado: false
    });

    const [temaConfigurado, setTemaConfigurado] = useState(() => {
        const savedPaletteId = Number(localStorage.getItem('ecommerce_palette'));
        return savedPaletteId || TEMA_PREDETERMINADO;
    });
    
    const navigate = useNavigate();

    // APLICAR COLORES ADAPTATIVOS
    useEffect(() => {
        aplicarPaleta(temaConfigurado);
    }, [temaConfigurado]);

    // Crear, marcar como principal o eliminar sube la versión y el efecto vuelve a pedir la lista
    const [versionDirecciones, setVersionDirecciones] = useState(0);
    const cargarDirecciones = () => {
        setCargando(true);
        setVersionDirecciones((version) => version + 1);
    };

    useEffect(() => {
        // Si se pide otra versión antes de que responda el servidor, la respuesta vieja se descarta
        let vigente = true;
        clienteAxios.get('ventas/direcciones/')
            .then(({ data }) => {
                if (!vigente) return;
                setDirecciones(data);
                setError('');
            })
            .catch((err) => {
                if (!vigente) return;
                console.error("Error cargando direcciones:", err);
                setError('No se pudieron cargar tus direcciones. Intenta de nuevo.');
            })
            .finally(() => {
                if (vigente) setCargando(false);
            });
        return () => { vigente = false; };
    }, [versionDirecciones]);

    // CARGAR CONFIGURACIÓN Y COMUNAS
    useEffect(() => {
        clienteAxios.get('configuracion/')
            .then(({ data }) => {
                const configDb = Array.isArray(data) ? data[0] : data;
                if (configDb?.tema_seleccionado !== undefined && configDb?.tema_seleccionado !== null) {
                    const idBackend = Number(configDb.tema_seleccionado);
                    if (!isNaN(idBackend)) {
                        setTemaConfigurado(idBackend);
                        localStorage.setItem('ecommerce_palette', idBackend.toString());
                    }
                }
            })
            .catch((error) => console.error('Error cargando configuración:', error));


        clienteAxios.get('ventas/logistica/comunas/')
            .then((response) => setListaComunas(response.data.comunas || []))
            .catch((err) => console.error("Error cargando comunas:", err))
            .finally(() => setCargandoComunas(false));
    }, []);

    const handleCrearDireccion = async (e) => {
        e.preventDefault();
        setError('');
        setMensajeExito('');
        
        try {
            await clienteAxios.post('ventas/direcciones/', nuevaDireccion);
            setMensajeExito('Dirección guardada exitosamente.');
            setMostrandoFormulario(false);
            setNuevaDireccion({ calle: '', calle_numero: '', dpto_casa: '', comuna: '', ciudad: '', region: '', es_predeterminado: false });
            cargarDirecciones();
        } catch (err) {
            setError('Hubo un error al guardar la dirección. Verifica los datos.');
            console.error(err);
        }
    };

    const marcarComoPrincipal = async (id) => {
        try {
            setError('');
            await clienteAxios.patch(`ventas/direcciones/${id}/`, { es_predeterminado: true });
            setMensajeExito('Dirección principal actualizada.');
            cargarDirecciones();
        } catch (err) {
            setError('No se pudo actualizar la dirección principal.');
            console.error(err);
        }
    };

    const eliminarDireccion = async (id) => {
        if (!window.confirm('¿Estás seguro de que deseas eliminar esta dirección?')) return;
        
        try {
            setError('');
            await clienteAxios.delete(`ventas/direcciones/${id}/`);
            setMensajeExito('Dirección eliminada correctamente.');
            cargarDirecciones();
        } catch (err) {
            setError('No se pudo eliminar la dirección.');
            console.error(err);
        }
    };

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        setNuevaDireccion({
            ...nuevaDireccion,
            [name]: type === 'checkbox' ? checked : value
        });
    };

    return (
        <>
            <Header />

            <main tabIndex={-1} id="contenido" className="direcciones-main">
                <div className="contenedor">
                    <button type="button" className="enlace-flecha direcciones-volver" onClick={() => navigate('/catalogo')}>
                        <span aria-hidden="true">←</span> Volver a la tienda
                    </button>

                    <div className="direcciones-encabezado">
                        <h1 className="direcciones-titulo">Mis direcciones de envío</h1>
                        {!mostrandoFormulario && (
                            <button type="button" className="boton boton-contorno" onClick={() => setMostrandoFormulario(true)}>
                                + Nueva dirección
                            </button>
                        )}
                    </div>

                    {error && <p role="alert" className="direcciones-aviso direcciones-aviso--error">{error}</p>}
                    {mensajeExito && <p role="status" className="direcciones-aviso direcciones-aviso--exito">{mensajeExito}</p>}

                    {/* FORMULARIO NUEVA DIRECCIÓN */}
                    {mostrandoFormulario && (
                        <section className="direcciones-formulario" aria-labelledby="direccion-nueva-titulo">
                            <h2 id="direccion-nueva-titulo">Agregar nueva dirección</h2>
                            <form onSubmit={handleCrearDireccion}>
                                <div className="direcciones-fila">
                                    <div className="direcciones-campo direcciones-campo--ancho">
                                        <label htmlFor="direccion-calle">Calle</label>
                                        <input id="direccion-calle" maxLength={255} type="text" name="calle" autoComplete="address-line1" value={nuevaDireccion.calle} onChange={handleChange} required placeholder="Ej: Av. Providencia" />
                                    </div>
                                    <div className="direcciones-campo">
                                        <label htmlFor="direccion-numero">Número</label>
                                        <input id="direccion-numero" maxLength={50} type="text" name="calle_numero" value={nuevaDireccion.calle_numero} onChange={handleChange} required placeholder="Ej: 1234" />
                                    </div>
                                </div>

                                <div className="direcciones-campo">
                                    <label htmlFor="direccion-dpto">Dpto, casa o referencia (opcional)</label>
                                    <input id="direccion-dpto" maxLength={100} type="text" name="dpto_casa" autoComplete="address-line2" value={nuevaDireccion.dpto_casa} onChange={handleChange} placeholder="Ej: Depto 505 / Casa 12 / Condominio Las Rosas" />
                                </div>

                                <div className="direcciones-fila">
                                    <div className="direcciones-campo">
                                        <label htmlFor="direccion-comuna">Comuna</label>
                                        <select
                                            id="direccion-comuna"
                                            name="comuna" value={nuevaDireccion.comuna} onChange={handleChange}
                                            required disabled={cargandoComunas}
                                        >
                                            <option value="">{cargandoComunas ? "Cargando..." : "-- Selecciona --"}</option>
                                            {listaComunas.map(c => <option key={c} value={c}>{c}</option>)}
                                        </select>
                                    </div>
                                    <div className="direcciones-campo">
                                        <label htmlFor="direccion-ciudad">Ciudad</label>
                                        <input id="direccion-ciudad" maxLength={100} type="text" name="ciudad" autoComplete="address-level2" value={nuevaDireccion.ciudad} onChange={handleChange} required placeholder="Ej: Santiago" />
                                    </div>
                                </div>

                                <div className="direcciones-campo">
                                    <label htmlFor="direccion-region">Región (opcional)</label>
                                    <input id="direccion-region" maxLength={100} type="text" name="region" autoComplete="address-level1" value={nuevaDireccion.region} onChange={handleChange} placeholder="Ej: Metropolitana" />
                                </div>

                                <label className="direcciones-casilla">
                                    <input type="checkbox" name="es_predeterminado" checked={nuevaDireccion.es_predeterminado} onChange={handleChange} />
                                    Establecer como dirección principal
                                </label>

                                <div className="direcciones-acciones-formulario">
                                    <button type="button" className="boton boton-contorno" onClick={() => setMostrandoFormulario(false)}>
                                        Cancelar
                                    </button>
                                    <button type="submit" className="boton boton-primario">
                                        Guardar dirección
                                    </button>
                                </div>
                            </form>
                        </section>
                    )}

                    {/* LISTADO DE DIRECCIONES */}
                    {cargando ? (
                        <Cargando texto="Cargando tus direcciones..."><EsqueletoLista elementos={2} /></Cargando>
                    ) : direcciones.length > 0 ? (
                        <ul className="lista-sin-estilo direcciones-lista">
                            {direcciones.map(dir => (
                                <li key={dir.id} className={`direccion${dir.es_predeterminado ? ' direccion--principal' : ''}`}>
                                    <div>
                                        <div className="direccion-cabecera">
                                            <h3>
                                                {dir.calle} {dir.calle_numero} {dir.dpto_casa && `- ${dir.dpto_casa}`}
                                            </h3>
                                            {dir.es_predeterminado && <span className="direccion-chip">Principal</span>}
                                        </div>
                                        <p className="direccion-detalle">{dir.comuna}, {dir.ciudad}</p>
                                        {dir.region && <p className="direccion-detalle">{dir.region}</p>}
                                    </div>

                                    <div className="direccion-acciones">
                                        {!dir.es_predeterminado && (
                                            <button type="button" className="direccion-enlace" onClick={() => marcarComoPrincipal(dir.id)}>
                                                Hacer principal
                                            </button>
                                        )}
                                        <button type="button" className="direccion-enlace direccion-enlace--peligro" onClick={() => eliminarDireccion(dir.id)}>
                                            Eliminar
                                        </button>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        !mostrandoFormulario && (
                            <div className="direcciones-vacio">
                                <p>Aún no tienes direcciones guardadas.</p>
                                <button type="button" className="boton boton-primario" onClick={() => setMostrandoFormulario(true)}>
                                    Agregar mi primera dirección
                                </button>
                            </div>
                        )
                    )}
                </div>
            </main>
        </>
    );
};

export default MisDirecciones;