import { useState, useEffect, useCallback, useRef } from 'react';
import clienteAxios from './auth/axiosConfig';
import { useNavigate } from 'react-router-dom';
import { ajustarCarrito, guardarCarrito, interpretarCarrito, leerSnapshotCarrito, vaciarCarrito, validarCarrito } from './carrito';
import useCarrito from '../hooks/useCarrito';
import { EMPRESA_VACIA, normalizarRut, validarDatosEmpresa } from '../utils/empresa';
import { cumpleMinimo, daEnvioGratis, elegirDescuento, montoDescuento, siguienteAutomatico } from '../utils/descuentos';
import { descuentoSuscriptor } from '../utils/suscripciones';
import { soloCaracteresDeTelefono } from '../utils/telefono';
import './Checkout.css';
import DatosEmpresa from './DatosEmpresa';
import LogoMedioPago from './LogoMedioPago';
import Header from './header/header';
import Dialogo from './Dialogo';
import { Bloque, Cargando } from './carga/Esqueleto';
import Spinner from './carga/Spinner';

const OPCION_RETIRO_LOCAL = {
    proveedor: 'RETIRO_LOCAL', nombre: 'Retiro en Tienda / Local', tipo: 'RETIRO', costo_envio: 0,
};

const formatoPesos = (monto) => Number(monto).toLocaleString('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 });

const NOMBRES_TIPO_DESPACHO = {
    DOMICILIO: 'A Domicilio',
    SUCURSAL: 'Retiro en sucursal',
    RETIRO_LOCAL: 'Retiro en Local',
    ENTREGA_COORDINADA: 'Entrega coordinada',
};

// Lo que el servidor necesita de cada producto: el peso y las medidas del paquete los toma del catálogo
const itemsParaElServidor = (items) => items.map(item => ({
    producto_mongo_id: item.id, variante_sku: item.sku, cantidad: item.cantidad,
}));

// Nombre que ve el comprador para cada código de medio de pago (RN-02: el backend solo envía los disponibles)
// Lo mínimo para avisar antes de pagar; el servidor lo valida de verdad (EmailField)
const CORREO_VALIDO = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
// Sin suscripción activa (o sin el módulo): ni descuento ni envío gratis
const SIN_BENEFICIOS = { descuento: 0, envio_gratis: false };

const NOMBRES_MEDIO_PAGO = {
    TRANSBANK: 'Webpay (Transbank)',
    MERCADO_PAGO: 'Mercado Pago',
    TRANSFERENCIA: 'Transferencia bancaria'
};

// Orden de Mercado Pago que espera su pago. El token firmado que entrega el checkout prueba que la creó este
// navegador: sin él, verificar-pago no responde (los números de orden son correlativos y se podrían adivinar)
const consultarPagoPendiente = (idOrden) => clienteAxios.get('ventas/checkout/verificar-pago/', {
    params: { orden_id: idOrden, token: localStorage.getItem('orden_pendiente_token') }
});

const olvidarOrdenPendiente = () => {
    localStorage.removeItem('orden_pendiente_pago');
    localStorage.removeItem('orden_pendiente_token');
};

export default function Checkout() {
    return (
        <>
            <Header />
            <main tabIndex={-1} id="contenido" className="checkout-main">
                <CheckoutContenido />
            </main>
        </>
    );
}

function CheckoutContenido() {
    const [modoAutenticacion, setModoAutenticacion] = useState(null);
    const [emailInvitado, setEmailInvitado] = useState('');
    // RF-02.3: quién recibe o retira el pedido (Chilexpress y la tienda lo contactan)
    const [nombreDestinatario, setNombreDestinatario] = useState('');
    const [telefonoDestinatario, setTelefonoDestinatario] = useState('');
    // Compra como empresa: la tienda emite la factura con estos datos
    const [compraEmpresa, setCompraEmpresa] = useState(false);
    const [datosEmpresa, setDatosEmpresa] = useState(EMPRESA_VACIA);
    const [erroresEmpresa, setErroresEmpresa] = useState({});
    const [guardarEmpresa, setGuardarEmpresa] = useState(true);
    const [mensaje, setMensaje] = useState('');
    const [errorReglas, setErrorReglas] = useState(false);
    const [opcionCompra, setOpcionCompra] = useState(null);
    const itemsCarrito = useCarrito();
    
    // --- CONFIGURACIÓN DE LA TIENDA (LOCAL) ---
    const [configTienda, setConfigTienda] = useState(null);

    // --- ESTADOS DE TIPO DE DESPACHO ---
    // 'DOMICILIO' | 'SUCURSAL' | 'RETIRO_LOCAL' | 'ENTREGA_COORDINADA'
    const [tipoElegido, setTipoDespacho] = useState('DOMICILIO');
    // RF-02.3: solo las entregas que ofrece la tienda; los couriers, si tienen sus llaves cargadas
    const couriers = configTienda?.couriers || [];
    const hayCouriers = couriers.length > 0;
    const couriersConSucursal = couriers.filter(courier => courier.sucursales);
    const tiposDisponibles = [
        ...(hayCouriers ? ['DOMICILIO'] : []),
        ...(couriersConSucursal.length > 0 ? ['SUCURSAL'] : []),
        ...(configTienda?.retiro_en_local_activo ? ['RETIRO_LOCAL'] : []),
        ...(configTienda?.entrega_coordinada_activa ? ['ENTREGA_COORDINADA'] : []),
    ];
    const tipoDespacho = tiposDisponibles.includes(tipoElegido) ? tipoElegido : (tiposDisponibles[0] ?? null);
    // En la entrega coordinada la tienda puede acordar la dirección con el comprador (domain/logistica.py)
    const direccionOpcional = tipoDespacho === 'ENTREGA_COORDINADA';
    const [comunaSucursal, setComunaSucursal] = useState('');
    // Con más de un courier con oficinas, el comprador elige de cuál; si no, el único
    const [codigoCourierSucursal, setCodigoCourierSucursal] = useState(null);
    const courierSucursal = couriersConSucursal.find(courier => courier.codigo === codigoCourierSucursal)
        || couriersConSucursal[0] || null;
    // A domicilio, cada courier cotiza y el comprador elige (sin elegir, el primero)
    const [proveedorElegido, setProveedorElegido] = useState(null);
    const [resultadoSucursales, setResultadoSucursales] = useState({ clave: null, items: [] });
    const [sucursalElegida, setSucursalElegida] = useState(null);

    // --- ESTADOS DE DIRECCIÓN DOMICILIO ---
    const [direccionesGuardadas, setDireccionesGuardadas] = useState([]);
    const [direccionSeleccionadaId, setDireccionSeleccionadaId] = useState('nueva');
    const [guardarNuevaDireccion, setGuardarNuevaDireccion] = useState(true);

    const [calle, setCalle] = useState('');
    const [numero, setNumero] = useState('');
    const [dptoCasa, setDptoCasa] = useState('');
    const [comuna, setComuna] = useState('');
    const [ciudad, setCiudad] = useState('');
    const region = '';

    const [listaComunas, setListaComunas] = useState([]);
    const [cargandoComunas, setCargandoComunas] = useState(true);
    const [pasarelas, setPasarelas] = useState([]);
    const [cargandoPagos, setCargandoPagos] = useState(true);

    // RF-04.1: el código que escribió el comprador (su regla, como la valida el servidor) y los descuentos automáticos.
    // No se suman: se muestra el que más ahorra, con el mismo cálculo que hace el servidor al pagar
    const [codigoEscrito, setCodigoEscrito] = useState(null);
    const [automaticos, setAutomaticos] = useState([]);
    const [beneficios, setBeneficios] = useState(SIN_BENEFICIOS);
    const [codigoInput, setCodigoInput] = useState('');
    // El comprador intentó pagar con datos faltantes: desde ahí se muestra junto a los botones qué le falta
    const [intentoPagar, setIntentoPagar] = useState(false);
    const [resultadoCotizacion, setResultadoCotizacion] = useState({ clave: null, opciones: [], error: '' });
    // RF-04.4: consentimiento obligatorio, desmarcado por defecto
    const [aceptaTerminos, setAceptaTerminos] = useState(false);
    // Tipos de página legal publicados (ej. 'TERMINOS'), para enlazarlos junto al consentimiento
    const [paginasLegales, setPaginasLegales] = useState([]);
    // Cambios hechos al carrito porque algo se agotó o cambió de precio
    const [revisionCarrito, setRevisionCarrito] = useState({ snapshot: null, avisos: [] });
    const avisosCarrito = revisionCarrito.snapshot === leerSnapshotCarrito() ? revisionCarrito.avisos : [];

    const usuarioAutenticado = !!localStorage.getItem('access_token');
    const [esperandoPago, setEsperandoPago] = useState(null);
    const [mostrarDialogoPago, setMostrarDialogoPago] = useState(false);
    const consultaEnCurso = useRef(false);
    // Con el pago confirmado no se consulta más: el cambio de ruta es una transición y el checkout sigue montado un
    // instante, en el que el intervalo podía volver a preguntar
    const pagoConfirmado = useRef(false);
    const botonReabrirPago = useRef(null);
    const cerrarAvisoPago = () => {
        setMostrarDialogoPago(false);
        // El disparador original queda deshabilitado mientras existe una orden pendiente.
        // Esperamos a que aparezca la acción que permite reabrir el mismo aviso.
        requestAnimationFrame(() => botonReabrirPago.current?.focus());
    };
    const [verificando, setVerificando] = useState(false);
    const [procesandoPago, setProcesandoPago] = useState(false);
    const navigate = useNavigate();

    const verificarEstadoOrden = useCallback(async (idOrden) => {
        if (!idOrden || consultaEnCurso.current || pagoConfirmado.current) return;
        consultaEnCurso.current = true;
        setVerificando(true);
        try {
            const res = await consultarPagoPendiente(idOrden);
            if (res.data.pagado) {
                pagoConfirmado.current = true;
                localStorage.removeItem('carrito_local');
                olvidarOrdenPendiente();
                window.dispatchEvent(new Event('carritoActualizado'));
                if (usuarioAutenticado) {
                    try { await clienteAxios.post('ventas/carrito/', { items: [] }); } catch { /* vaciado silencioso */ }
                }
                const sufijoRevision = res.data.requiere_revision ? '&revision=1' : '';
                navigate(`/pago-exitoso?orden=${idOrden}${sufijoRevision}`);
            } else if (res.data.cancelado) {
                setEsperandoPago(null);
                olvidarOrdenPendiente();
                setMensaje('La orden fue cancelada o rechazada.');
            }
        } catch (err) {
            console.error('Error verificando pago:', err);
        } finally {
            consultaEnCurso.current = false;
            setVerificando(false);
        }
    }, [usuarioAutenticado, navigate]);

    // Polling cada 3 segundos si esperandoPago está activo
    useEffect(() => {
        if (!esperandoPago?.ordenId) return;
        const interval = setInterval(() => {
            verificarEstadoOrden(esperandoPago.ordenId);
        }, 3000);
        return () => clearInterval(interval);
    }, [esperandoPago?.ordenId, verificarEstadoOrden]);

    // Los descuentos automáticos vigentes (sin sus códigos); si falla, el checkout sigue sin la vista previa
    useEffect(() => {
        clienteAxios.get('ventas/promociones/automaticas/')
            .then(({ data }) => setAutomaticos(Array.isArray(data) ? data : []))
            .catch(() => setAutomaticos([]));
    }, []);

    // Suscripciones (pedido de un cliente, opcional): el descuento y el envío gratis de su suscripción activa. Solo
    // para la vista previa: el servidor los vuelve a calcular al comprar
    useEffect(() => {
        if (!usuarioAutenticado || !configTienda?.suscripciones_activas) return;
        clienteAxios.get('ventas/suscripciones/beneficios/')
            .then(({ data }) => setBeneficios({ descuento: Number(data?.descuento) || 0, envio_gratis: Boolean(data?.envio_gratis) }))
            .catch(() => setBeneficios(SIN_BENEFICIOS));
    }, [usuarioAutenticado, configTienda?.suscripciones_activas]);

    // Verificación de orden pendiente al cargar la página
    useEffect(() => {
        const ordenPendiente = localStorage.getItem('orden_pendiente_pago');
        if (ordenPendiente) {
            consultarPagoPendiente(ordenPendiente)
                .then(res => {
                    if (res.data.pagado) {
                        localStorage.removeItem('carrito_local');
                        olvidarOrdenPendiente();
                        window.dispatchEvent(new Event('carritoActualizado'));
                        const sufijoRevision = res.data.requiere_revision ? '&revision=1' : '';
                        navigate(`/pago-exitoso?orden=${ordenPendiente}${sufijoRevision}`);
                    }
                })
                .catch(() => {});
        }
    }, [navigate]);

    // 1. CARGA INICIAL: Configuración de la tienda, Pasarelas y Comunas
    useEffect(() => {
        clienteAxios.get('configuracion/')
            .then(res => {
                const config = Array.isArray(res.data) ? res.data[0] : res.data;
                setPasarelas(config?.pasarelas_activas || []);
                setConfigTienda(config);
            })
            .catch(() => setMensaje('No se pudo cargar la configuración de la tienda.'))
            .finally(() => setCargandoPagos(false));

        clienteAxios.get('ventas/checkout/reglas/')
            .then(res => {
                setModoAutenticacion(res.data.modo_autenticacion);
            })
            .catch(() => {
                setMensaje('No se pudieron cargar las opciones de compra.');
                setErrorReglas(true);
            });

        // Sin enlaces el checkbox sigue funcionando: solo se pierde la opción de leerlas aquí
        clienteAxios.get('ventas/paginas-legales/')
            .then(res => setPaginasLegales((res.data || []).map(p => p.tipo_pagina)))
            .catch(() => setPaginasLegales([]));
    }, []);

    // Las comunas con cobertura vienen de los couriers activos: sin ellos, la comuna se escribe a mano
    useEffect(() => {
        if (!hayCouriers) return;
        clienteAxios.get('ventas/logistica/comunas/')
            .then(res => setListaComunas(res.data.comunas || []))
            .catch(() => setMensaje('No se pudieron cargar las comunas de envío.'))
            .finally(() => setCargandoComunas(false));
    }, [hayCouriers]);

    const enlaceLegal = (tipo, texto) => paginasLegales.includes(tipo) ? (
        <a href={`/legal/${tipo.toLowerCase()}`} target="_blank" rel="noopener noreferrer" aria-label={`${texto} (se abre en otra pestaña)`}>
            {texto}
        </a>
    ) : texto;

    // Con sesión, quién recibe se precarga con los datos de la cuenta (el comprador puede cambiarlos)
    useEffect(() => {
        if (!usuarioAutenticado) return;
        clienteAxios.get('usuarios/me/')
            .then(({ data }) => {
                // Algunas cuentas (ej. creadas con Google) ya traen el apellido dentro del nombre
                const nombre = (data.nombre || '').trim();
                const apellido = (data.apellido_paterno || '').trim();
                const completo = !apellido || nombre.toLowerCase().includes(apellido.toLowerCase())
                    ? nombre : `${nombre} ${apellido}`;
                setNombreDestinatario(actual => actual || completo);
                setTelefonoDestinatario(actual => actual || data.telefono || '');
            })
            .catch(() => {});
    }, [usuarioAutenticado]);

    // Con sesión, los datos de la empresa que el comprador guardó en una compra anterior (204 si no hay)
    useEffect(() => {
        if (!usuarioAutenticado) return;
        clienteAxios.get('ventas/empresa/')
            .then(({ data }) => {
                if (data && typeof data === 'object') setDatosEmpresa(actual => ({ ...actual, ...data }));
            })
            .catch(() => {});
    }, [usuarioAutenticado]);

    const editarEmpresa = (campo, valor) => {
        setDatosEmpresa(actual => ({ ...actual, [campo]: valor }));
        setErroresEmpresa(actual => ({ ...actual, [campo]: undefined }));
    };

    // 2. CARGA DE DIRECCIONES GUARDADAS
    // Las direcciones se cargan por sesión, sin reiniciar la elección al cambiar el carrito.
    useEffect(() => {
        let vigente = true;
        if (usuarioAutenticado) {
            clienteAxios.get('ventas/direcciones/')
                .then(res => {
                    if (!vigente) return;
                    const direcciones = res.data;
                    setDireccionesGuardadas(direcciones);
                    if (direcciones.length > 0) {
                        const predeterminada = direcciones.find(d => d.es_predeterminado) || direcciones[0];
                        setDireccionSeleccionadaId(predeterminada.id);
                    }
                })
                .catch(err => console.error(err));
        }
        return () => { vigente = false; };
    }, [usuarioAutenticado]);

    // RN-03: ajusta el carrito al stock y precios vigentes y avisa qué cambió.
    // Si la validación falla, se sigue con el carrito tal cual: el backend revalida al crear la orden.
    const revisarCarrito = useCallback(async () => {
        const snapshot = leerSnapshotCarrito();
        const items = interpretarCarrito(snapshot);
        if (items.length === 0) return null;
        try {
            const ajuste = ajustarCarrito(items, await validarCarrito(items));
            if (snapshot !== leerSnapshotCarrito()) return null;
            if (ajuste.avisos.length > 0 && JSON.stringify(ajuste.items) !== JSON.stringify(items)) {
                return { ...ajuste, snapshot };
            }
        } catch (error) {
            console.error('No se pudo validar el carrito:', error);
        }
        return null;
    }, []);

    // Cada versión se valida; una respuesta anterior no puede reemplazar el carrito actual.
    useEffect(() => {
        let vigente = true;
        revisarCarrito().then(ajuste => {
            if (!vigente || !ajuste || ajuste.snapshot !== leerSnapshotCarrito()) return;
            setRevisionCarrito({ snapshot: JSON.stringify(ajuste.items), avisos: ajuste.avisos });
            guardarCarrito(ajuste.items);
        });
        return () => { vigente = false; };
    }, [itemsCarrito, revisarCarrito]);

    // Las sucursales y su selección pertenecen a un courier y una comuna concretos.
    const claveSucursales = tipoDespacho === 'SUCURSAL' && comunaSucursal && courierSucursal
        ? `${courierSucursal.codigo}|${comunaSucursal}` : null;
    useEffect(() => {
        if (!claveSucursales) return;
        const [proveedor, comunaBuscada] = claveSucursales.split('|');
        let vigente = true;
        const controller = new AbortController();
        clienteAxios.get(`ventas/logistica/sucursales/?comuna=${encodeURIComponent(comunaBuscada)}&proveedor=${proveedor}`, { signal: controller.signal })
            .then(res => {
                if (vigente) setResultadoSucursales({ clave: claveSucursales, items: res.data.sucursales || [] });
            })
            .catch(() => {
                if (vigente) setResultadoSucursales({ clave: claveSucursales, items: [] });
            });
        return () => { vigente = false; controller.abort(); };
    }, [claveSucursales]);

    const sucursalesDisponibles = claveSucursales && resultadoSucursales.clave === claveSucursales ? resultadoSucursales.items : [];
    const cargandoSucursales = !!claveSucursales && resultadoSucursales.clave !== claveSucursales;
    const sucursalSeleccionada = sucursalElegida?.clave === claveSucursales ? sucursalElegida : null;
    const direccionGuardada = direccionesGuardadas.find(dir => dir.id === direccionSeleccionadaId);
    const destinoEnvio = tipoDespacho === 'SUCURSAL' ? comunaSucursal
        : tipoDespacho === 'DOMICILIO' ? (direccionSeleccionadaId === 'nueva' ? comuna : direccionGuardada?.comuna || '') : '';
    // En sucursal cotiza solo el courier de la oficina; a domicilio, todos los activos
    const proveedorCotizado = tipoDespacho === 'SUCURSAL' ? courierSucursal?.codigo || null : null;
    const claveCotizacion = destinoEnvio.trim() && itemsCarrito.length > 0
        ? JSON.stringify([tipoDespacho, destinoEnvio.trim().toUpperCase(), itemsCarrito, proveedorCotizado]) : null;

    // El estado de carga se deriva de la clave: nunca se ofrece la cotización de otro carrito.
    useEffect(() => {
        if (!claveCotizacion) return;
        const [tipo, destino, items, proveedor] = JSON.parse(claveCotizacion);
        let vigente = true;
        const controller = new AbortController();
        clienteAxios.post('ventas/logistica/cotizar/', {
            destino, items: itemsParaElServidor(items),
            ...(proveedor ? { proveedor } : {}),
        }, { signal: controller.signal })
            .then(({ data }) => {
                if (!vigente) return;
                setResultadoCotizacion({
                    clave: claveCotizacion,
                    opciones: (data.opciones || []).map(opcion => ({
                        proveedor: opcion.proveedor,
                        nombre: opcion.tiempo_estimado ? `${opcion.nombre} - ${opcion.tiempo_estimado}` : opcion.nombre,
                        tipo: tipo === 'SUCURSAL' ? 'RETIRO' : 'DOMICILIO', costo_envio: Number(opcion.precio),
                    })),
                    error: '',
                });
            })
            .catch(error => {
                if (vigente) setResultadoCotizacion({
                    clave: claveCotizacion, opciones: [],
                    error: error.response?.data?.error || 'No se pudo calcular el costo de envío.',
                });
            });
        return () => { vigente = false; controller.abort(); };
    }, [claveCotizacion]);

    const cotizacionVigente = claveCotizacion && resultadoCotizacion.clave === claveCotizacion ? resultadoCotizacion : null;
    const cotizando = !!claveCotizacion && !cotizacionVigente;
    // Retiro y entrega coordinada los hace la tienda: no se cotizan, su costo lo define el admin
    const opcionEntregaPropia = tipoDespacho === 'RETIRO_LOCAL' ? OPCION_RETIRO_LOCAL
        : tipoDespacho === 'ENTREGA_COORDINADA' ? {
            proveedor: 'ENTREGA_COORDINADA', nombre: 'Entrega coordinada', tipo: 'COORDINADA',
            costo_envio: Number(configTienda?.costo_entrega_coordinada) || 0,
        } : null;
    const opcionesCourier = cotizacionVigente?.opciones || [];
    const opcionEntregaSeleccionada = opcionEntregaPropia && itemsCarrito.length > 0 ? opcionEntregaPropia
        : opcionesCourier.find(opcion => opcion.proveedor === proveedorElegido) || opcionesCourier[0] || null;
    // Con varios couriers cotizados el comprador elige; con uno solo (o una entrega de la tienda) solo se informa
    const opcionesEntrega = opcionEntregaPropia ? (opcionEntregaSeleccionada ? [opcionEntregaSeleccionada] : [])
        : opcionesCourier;
    const costoEnvio = Number(opcionEntregaSeleccionada?.costo_envio || 0);
    const mensajeVisible = mensaje || cotizacionVigente?.error || '';


    const irALogin = () => { localStorage.setItem('url_anterior_login', window.location.pathname); navigate('/login'); };

    const compraComoInvitado = modoAutenticacion === 'INVITADO' || (modoAutenticacion === 'MIXTO' && opcionCompra === 'INVITADO');
    const subtotal = itemsCarrito.reduce((acc, item) => acc + (Number(item.precio) * Number(item.cantidad)), 0);
    const descuentoElegido = elegirDescuento(codigoEscrito ? [codigoEscrito, ...automaticos] : automaticos,
        subtotal, costoEnvio);
    const montoDescontado = descuentoElegido ? montoDescuento(descuentoElegido, subtotal) : 0;
    const tieneEnvioGratisCupon = Boolean(descuentoElegido && daEnvioGratis(descuentoElegido, subtotal));
    // "Te faltan $X": el automático más cercano que todavía no se alcanza
    const proximoAutomatico = siguienteAutomatico(automaticos, subtotal);
    // Suscriptor: su descuento sobre lo que queda después del cupón, y envío gratis si su plan lo da
    const baseConCupon = Math.max(0, subtotal - montoDescontado);
    const montoSuscriptor = usuarioAutenticado ? descuentoSuscriptor(baseConCupon, beneficios.descuento) : 0;
    const envioGratisSuscriptor = usuarioAutenticado && beneficios.envio_gratis;
    const tieneEnvioGratis = tieneEnvioGratisCupon || envioGratisSuscriptor;
    const costoEnvioFinal = tieneEnvioGratis ? 0 : costoEnvio;
    const totalFinal = Math.max(0, baseConCupon - montoSuscriptor) + costoEnvioFinal;

    // El cupón se valida en el servidor (vigencia incluida) y su código viaja en el checkout, donde el
    // servidor vuelve a validarlo y lo descuenta del total: lo que se muestra aquí es solo una vista previa
    const aplicarCodigo = async () => {
        const codigo = codigoInput.trim().toUpperCase();
        if (!codigo) return;

        try {
            const { data } = await clienteAxios.post('ventas/promociones/validar/', { codigo, subtotal });
            const regla = {
                codigo: data.codigo, tipo_descuento: data.tipo_descuento, valor_descuento: data.valor_descuento,
                monto_minimo: data.monto_minimo, umbral_envio_gratis: data.umbral_envio_gratis,
            };
            setCodigoEscrito(regla);
            // No se suman: si un descuento automático ahorra más, se queda ese y se avisa
            setMensaje(elegirDescuento([regla, ...automaticos], subtotal, costoEnvio) === regla
                ? '¡Código aplicado con Éxito!'
                : 'Tu compra ya tiene un descuento mayor, así que se aplica ese (los descuentos no se suman).');
        } catch (error) {
            setCodigoEscrito(null);
            setMensaje(error.response?.data?.error || 'Código inválido o expirado.');
        }
    };
    // Lo que falta para pagar, en el orden del formulario: { texto, selector del campo a enfocar }
    const faltantesParaPagar = () => {
        const faltan = [];
        const agregar = (texto, selector) => faltan.push({ texto, selector });
        if (itemsCarrito.length === 0) agregar('agregar productos al carrito', null);
        if (!usuarioAutenticado && compraComoInvitado) {
            if (!emailInvitado.trim()) agregar('tu correo electrónico', '#checkout-email');
            else if (!CORREO_VALIDO.test(emailInvitado.trim())) agregar('un correo electrónico válido', '#checkout-email');
        }
        if (!nombreDestinatario.trim()) agregar('el nombre de quien recibe', '#checkout-destinatario');
        if (!telefonoDestinatario.trim()) agregar('el teléfono de contacto', '#checkout-telefono');
        if (compraEmpresa) {
            const errores = validarDatosEmpresa(datosEmpresa);
            const primero = Object.keys(errores)[0];
            if (primero) agregar('los datos de la empresa para la factura', `#checkout-empresa-${primero}`);
        }
        if (tipoDespacho === 'SUCURSAL') {
            if (!comunaSucursal) agregar('la comuna de la sucursal', '#checkout-comuna-sucursal');
            else if (!sucursalSeleccionada) agregar('la sucursal donde retiras', 'input[name="sucursal"]');
        } else if ((tipoDespacho === 'DOMICILIO' || direccionOpcional) && direccionSeleccionadaId === 'nueva') {
            // La entrega coordinada puede ir sin dirección; si se escribe, con calle y comuna
            const escribioAlgo = [calle, numero, comuna].some(valor => valor.trim());
            if (!direccionOpcional || escribioAlgo) {
                if (!calle.trim()) agregar('la calle', '#checkout-calle');
                if (!direccionOpcional && !numero.trim()) agregar('el número', '#checkout-numero');
                if (!comuna.trim()) agregar('la comuna', '#checkout-comuna');
                if (!direccionOpcional && !ciudad.trim()) agregar('la ciudad', '#checkout-ciudad');
            }
        }
        if (!opcionEntregaSeleccionada && !cotizando && faltan.every(f => !f.selector?.startsWith('#checkout-comuna'))) {
            agregar('una forma de entrega con costo calculado', 'input[name="tipo-despacho"]');
        }
        if (!aceptaTerminos) agregar('aceptar los Términos y Condiciones y la Política de Privacidad', '#checkout-terminos');
        return faltan;
    };
    const faltantes = faltantesParaPagar();

    // Con datos faltantes el botón no paga: avisa qué falta junto a los botones y lleva al primer campo
    const intentarPagar = (metodoSeleccionado) => {
        if (faltantes.length === 0) {
            setIntentoPagar(false);
            procesarPago(metodoSeleccionado);
            return;
        }
        setIntentoPagar(true);
        if (compraEmpresa) setErroresEmpresa(validarDatosEmpresa(datosEmpresa));
        const primero = faltantes.find(f => f.selector)?.selector;
        const campo = primero && document.querySelector(primero);
        if (campo) {
            campo.focus({ preventScroll: true });
            campo.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
        }
    };

    const procesarPago = async (metodoSeleccionado) => {
        const snapshotPedido = leerSnapshotCarrito();
        if (itemsCarrito.length === 0) return setMensaje('Tu carrito está vacío.');
        if (!opcionEntregaSeleccionada) return setMensaje('Selecciona una opción de entrega.');
        if (!nombreDestinatario.trim() || !telefonoDestinatario.trim()) return setMensaje('Indica el nombre y el teléfono de quien recibe el pedido.');
        if (!aceptaTerminos) return setMensaje('Debes aceptar los Términos y Condiciones y la Política de Privacidad.');
        if (compraEmpresa) {
            const errores = validarDatosEmpresa(datosEmpresa);
            if (Object.keys(errores).length > 0) {
                setErroresEmpresa(errores);
                return setMensaje('Revisa los datos de la empresa para la factura.');
            }
        }

        let dirSnapshot;
        
        if (tipoDespacho === 'RETIRO_LOCAL') {
            dirSnapshot = {
                calle: `Retiro en Local: ${configTienda?.calle_origen || 'Av. Principal'}`,
                numero: configTienda?.numero_origen || '123',
                dpto_casa: configTienda?.dpto_casa_origen ? `Oficina/Detalle: ${configTienda.dpto_casa_origen}` : 'Retiro en Tienda Física',
                comuna: configTienda?.comuna_origen || 'Santiago',
                ciudad: configTienda?.comuna_origen || 'Santiago',
                region: configTienda?.region_origen || 'Metropolitana'
            };
        } else if (tipoDespacho === 'SUCURSAL') {
            if (!comunaSucursal || !sucursalSeleccionada) {
                return setMensaje('Debes elegir una sucursal para el retiro.');
            }
            dirSnapshot = {
                calle: `Agencia ${courierSucursal.nombre}: ${sucursalSeleccionada.nombre}`,
                numero: 'S/N',
                dpto_casa: `Código Oficial: ${sucursalSeleccionada.codigo}`,
                // La orden de transporte se entrega en esta oficina del courier
                codigo_sucursal: sucursalSeleccionada.codigo,
                comuna: comunaSucursal,
                ciudad: comunaSucursal,
                region: ''
            };
        } else {
            if (direccionSeleccionadaId !== 'nueva') {
                const dir = direccionesGuardadas.find(d => d.id === direccionSeleccionadaId);
                dirSnapshot = { calle: dir.calle, numero: dir.calle_numero, dpto_casa: dir.dpto_casa, comuna: dir.comuna, ciudad: dir.ciudad, region: dir.region };
            } else if (direccionOpcional && ![calle, numero, comuna].some(valor => valor.trim())) {
                // RF-02.3: la entrega coordinada puede ir sin dirección; la tienda la acuerda con el comprador
                dirSnapshot = {};
            } else {
                if (direccionOpcional ? !calle.trim() || !comuna.trim()
                    : !calle.trim() || !numero.trim() || !comuna.trim() || !ciudad.trim()) {
                    return setMensaje(direccionOpcional
                        ? 'Completa la calle y la comuna, o deja la dirección vacía para acordarla con la tienda.'
                        : 'Completa todos los campos obligatorios de tu nueva dirección de envío.');
                }
                dirSnapshot = { calle, numero, dpto_casa: dptoCasa, comuna, ciudad, region };

                // Una dirección incompleta (sin número o ciudad) sirve para esta entrega, pero no se guarda
                if (usuarioAutenticado && guardarNuevaDireccion && numero.trim() && ciudad.trim()) {
                    try {
                        await clienteAxios.post('ventas/direcciones/', { calle, calle_numero: numero, dpto_casa: dptoCasa, comuna, ciudad, region, es_predeterminado: true });
                    } catch (err) { console.error(err); }
                }
            }
        }
        
        if (procesandoPago) return;
        if (snapshotPedido !== leerSnapshotCarrito()) {
            return setMensaje('El carrito cambió. Revisa el resumen antes de pagar.');
        }
        setProcesandoPago(true);
        setMensaje('Procesando...');

        const payload = {
            metodo_pago: metodoSeleccionado, 
            email_invitado: !usuarioAutenticado && compraComoInvitado ? emailInvitado : null,
            nombre_destinatario: nombreDestinatario.trim(),
            telefono_destinatario: telefonoDestinatario.trim(),
            datos_empresa: compraEmpresa ? { ...datosEmpresa, rut: normalizarRut(datosEmpresa.rut) } : null,
            guardar_datos_empresa: compraEmpresa && usuarioAutenticado && guardarEmpresa,
            direccion_envio_snapshot: dirSnapshot,
            subtotal, 
            costo_envio: costoEnvioFinal, 
            total_final: totalFinal,
            proveedor_logistico: opcionEntregaSeleccionada.proveedor,
            acepta_terminos: aceptaTerminos,
            // El servidor vuelve a validar el código y elige el descuento; bajo su mínimo, el código no se envía
            codigo_promocion: codigoEscrito && cumpleMinimo(codigoEscrito, subtotal) ? codigoEscrito.codigo : null,
            items: itemsParaElServidor(itemsCarrito)
        };
        try {
            const respuesta = await clienteAxios.post('ventas/checkout/', payload);

            if (respuesta.data.url_pago) {
                if (metodoSeleccionado === 'MERCADO_PAGO') {
                    localStorage.setItem('orden_pendiente_pago', respuesta.data.orden_id);
                    localStorage.setItem('orden_pendiente_token', respuesta.data.token_verificacion);
                    setEsperandoPago({ ordenId: respuesta.data.orden_id, urlPago: respuesta.data.url_pago });
                    setMostrarDialogoPago(true);
                    const ventana = window.open(respuesta.data.url_pago, '_blank');
                    if (!ventana) {
                        window.location.assign(respuesta.data.url_pago);
                    }
                } else {
                    window.location.assign(respuesta.data.url_pago);
                }
            } else {
                if (snapshotPedido === leerSnapshotCarrito()) await vaciarCarrito();
                // Sin pasarela (ej. transferencia) la orden queda Pendiente; el invitado no tiene /mis-pedidos
                // Con transferencia, el backend envía los datos bancarios para mostrarlos de inmediato
                navigate(`/pedido-recibido?orden=${encodeURIComponent(respuesta.data.orden_id)}`, {
                    replace: true,
                    state: { instrucciones: respuesta.data.instrucciones_pago || null }
                });
            }
        } catch (error) {
            const datos = error.response?.data || {};

            // Si cambiaron los precios, se actualiza el carrito para que el comprador vea el nuevo total
            if (datos.precios_vigentes && snapshotPedido === leerSnapshotCarrito()) {
                const carritoActualizado = itemsCarrito.map(item => {
                    const vigente = datos.precios_vigentes.find(p => p.variante_sku === item.sku);
                    return vigente ? { ...item, precio: vigente.precio } : item;
                });
                await guardarCarrito(carritoActualizado);
            }

            // Algo se agotó mientras completaba el formulario: se ajusta el carrito y se le avisa
            if (datos.items) {
                const ajuste = await revisarCarrito();
                if (ajuste && ajuste.snapshot === leerSnapshotCarrito()) {
                    setRevisionCarrito({ snapshot: JSON.stringify(ajuste.items), avisos: ajuste.avisos });
                    await guardarCarrito(ajuste.items);
                }
            }
            // El backend también valida los datos de la empresa: sus errores van junto a cada campo
            if (datos.datos_empresa && typeof datos.datos_empresa === 'object') {
                setErroresEmpresa(Object.fromEntries(Object.entries(datos.datos_empresa)
                    .map(([campo, mensajes]) => [campo, [].concat(mensajes).join(' ')])));
            }
            const detalle = datos.subtotal || datos.items || datos.acepta_terminos || datos.metodo_pago
                || datos.nombre_destinatario || datos.telefono_destinatario
                || (datos.datos_empresa && 'Revisa los datos de la empresa para la factura.');
            setMensaje(detalle ? [].concat(detalle).join(' ') : 'Error al procesar la compra.');
            console.error(datos);
        } finally {
            setProcesandoPago(false);
        }
    };

    if (modoAutenticacion == null) {
        if (errorReglas) {
            return (
                <p role="alert" className="checkout-estado">
                    No se pudieron cargar las opciones de compra.
                </p>
            );
        }

        return (
            <p role={mensaje ? 'alert' : undefined} className="checkout-estado">
                {mensaje || 'Cargando...'}
            </p>
        );
    }

    // RN-04: según el modo de la tienda, primero se elige cómo comprar
    if (modoAutenticacion === 'REGISTRO_OBLIGATORIO' && !usuarioAutenticado) return (
        <div className="checkout-card checkout-acceso">
            <span className="antetitulo">Compra segura</span>
            <h1 className="checkout-titulo">Finalizar Compra</h1>
            <p className="texto-secundario">Para comprar en esta tienda necesitas una cuenta.</p>
            <button type="button" className="boton boton-primario" onClick={irALogin}>Iniciar sesión o registrarse</button>
        </div>
    );
    if (modoAutenticacion === 'MIXTO' && !usuarioAutenticado && opcionCompra === null) return (
        <div className="checkout-card checkout-acceso">
            <span className="antetitulo">Compra segura</span>
            <h1 className="checkout-titulo">Finalizar Compra</h1>
            <p className="texto-secundario">Puedes comprar solo con tu correo o entrar a tu cuenta.</p>
            <button type="button" className="boton boton-primario" onClick={() => setOpcionCompra('INVITADO')}>Comprar como invitado</button>
            <button type="button" className="boton boton-contorno" onClick={irALogin}>Iniciar sesión o registrarse</button>
        </div>
    );

    const claseOpcion = (elegida) => `checkout-opcion${elegida ? ' checkout-opcion--elegida' : ''}`;
    const exito = mensajeVisible.includes('Éxito');

    return (
        <div className="checkout-card checkout">
            <div className="checkout-encabezado">
                <span className="antetitulo">Compra segura</span>
                <h1 className="checkout-titulo">Finalizar Compra</h1>
            </div>

            {mensajeVisible && (
                <div role="status" className={`checkout-aviso ${exito ? 'checkout-aviso--exito' : 'checkout-aviso--error'}`}>
                    {mensajeVisible}
                </div>
            )}
            {avisosCarrito.length > 0 && (
                <div role="alert" className="checkout-aviso checkout-aviso--advertencia">
                    <strong>Actualizamos tu carrito:</strong>
                    <ul>
                        {avisosCarrito.map(aviso => <li key={aviso}>{aviso}</li>)}
                    </ul>
                </div>
            )}

            <div className="checkout-columnas">
                <form className="checkout-formulario" onSubmit={(e) => e.preventDefault()}>
                    {compraComoInvitado && (
                        <section className="checkout-seccion" aria-labelledby="checkout-paso-contacto">
                            <h2 id="checkout-paso-contacto" className="checkout-paso">Contacto</h2>
                            <div className="checkout-campo">
                                <label htmlFor="checkout-email">Correo electrónico para el recibo y estado de envío:</label>
                                <input id="checkout-email" type="email" autoComplete="email" value={emailInvitado} onChange={(e) => setEmailInvitado(e.target.value)} required />
                            </div>
                        </section>
                    )}

                    <fieldset className="checkout-grupo checkout-seccion">
                        <legend className="checkout-paso">¿Quién recibe el pedido?</legend>
                        <div className="checkout-campo">
                            <label htmlFor="checkout-destinatario">Nombre de quien recibe o retira</label>
                            <input id="checkout-destinatario" type="text" autoComplete="name" maxLength={120} value={nombreDestinatario} onChange={(e) => setNombreDestinatario(e.target.value)} required />
                        </div>
                        <div className="checkout-campo">
                            <label htmlFor="checkout-telefono">Teléfono de contacto</label>
                            <input id="checkout-telefono" type="tel" inputMode="tel" autoComplete="tel" maxLength={30} value={telefonoDestinatario} onChange={(e) => setTelefonoDestinatario(soloCaracteresDeTelefono(e.target.value))} required aria-describedby="checkout-telefono-ayuda" placeholder="+56 9 1234 5678" />
                            <p id="checkout-telefono-ayuda" className="checkout-ayuda">
                                Teléfono chileno de 9 dígitos. Lo usamos solo para coordinar la entrega.
                            </p>
                        </div>
                    </fieldset>

                    {/* Compra como empresa: la tienda emite la factura con estos datos */}
                    <fieldset className="checkout-grupo checkout-seccion">
                        <legend className="checkout-paso">Facturación</legend>
                        <label className="checkout-casilla">
                            <input type="checkbox" checked={compraEmpresa} onChange={(e) => { setCompraEmpresa(e.target.checked); setErroresEmpresa({}); }} aria-describedby="checkout-empresa-ayuda" />
                            Compro como empresa y necesito factura
                        </label>
                        <p id="checkout-empresa-ayuda" className="checkout-ayuda">
                            Te pediremos la razón social, el RUT, el giro y a qué correo enviar la factura.
                        </p>
                        {compraEmpresa && (
                            <>
                                <DatosEmpresa id="checkout-empresa" datos={datosEmpresa} errores={erroresEmpresa} onChange={editarEmpresa} />
                                {usuarioAutenticado && (
                                    <label className="checkout-casilla">
                                        <input type="checkbox" checked={guardarEmpresa} onChange={(e) => setGuardarEmpresa(e.target.checked)} />
                                        Guardar los datos de la empresa para mis próximas compras
                                    </label>
                                )}
                            </>
                        )}
                    </fieldset>

                    {/* --- ¿CÓMO DESEAS RECIBIR TU PEDIDO? --- */}
                    <fieldset className="checkout-grupo checkout-seccion">
                        <legend className="checkout-paso">¿Cómo deseas recibir tu pedido?</legend>
                        {tiposDisponibles.length > 0 ? (
                            <div className="checkout-fila checkout-opciones">
                                {tiposDisponibles.map(tipo => (
                                    <label key={tipo} className={claseOpcion(tipoDespacho === tipo)}>
                                        <input type="radio" name="tipo-despacho" value={tipo} checked={tipoDespacho === tipo} onChange={() => setTipoDespacho(tipo)} className="checkout-radio-oculto" />
                                        {tipo === 'SUCURSAL' && couriersConSucursal.length === 1
                                            ? `Sucursal ${couriersConSucursal[0].nombre}` : NOMBRES_TIPO_DESPACHO[tipo]}
                                    </label>
                                ))}
                            </div>
                        ) : configTienda && (
                            <p className="checkout-aviso checkout-aviso--error">
                                Esta tienda todavía no tiene formas de entrega disponibles.
                            </p>
                        )}

                        {/* --- CONTENIDO SEGÚN LA FORMA DE ENTREGA --- */}
                        {tipoDespacho === 'DOMICILIO' || tipoDespacho === 'ENTREGA_COORDINADA' ? (
                            <div className="checkout-entrega">
                                {direccionOpcional && (
                                    <>
                                        <p className="checkout-ayuda checkout-entrega-coordinada">
                                            {configTienda?.instrucciones_entrega_coordinada?.trim() || 'La tienda te contactará para acordar el día y la hora de la entrega.'}
                                        </p>
                                        <p className="checkout-ayuda">
                                            La dirección es opcional: si prefieres, déjala en blanco y la acuerdas con la tienda.
                                        </p>
                                    </>
                                )}
                                {usuarioAutenticado && direccionesGuardadas.length > 0 && (
                                    <fieldset className="checkout-grupo checkout-direcciones">
                                        <legend className="checkout-solo-lector">Dirección de envío</legend>
                                        {direccionesGuardadas.map(dir => (
                                            <label key={dir.id} className={claseOpcion(direccionSeleccionadaId === dir.id) + ' checkout-opcion--fila'}>
                                                <input type="radio" name="direccion-envio" value={dir.id} checked={direccionSeleccionadaId === dir.id} onChange={() => setDireccionSeleccionadaId(dir.id)} />
                                                <span>
                                                    <strong>{dir.calle} {dir.calle_numero} {dir.dpto_casa && `- ${dir.dpto_casa}`}</strong>
                                                    <span className="checkout-ayuda">{dir.comuna}, {dir.ciudad}</span>
                                                </span>
                                            </label>
                                        ))}
                                        <label className={claseOpcion(direccionSeleccionadaId === 'nueva') + ' checkout-opcion--fila'}>
                                            <input type="radio" name="direccion-envio" value="nueva" checked={direccionSeleccionadaId === 'nueva'} onChange={() => setDireccionSeleccionadaId('nueva')} />
                                            <strong>Ingresar una nueva dirección</strong>
                                        </label>
                                    </fieldset>
                                )}

                                {direccionSeleccionadaId === 'nueva' && (
                                    <div className="checkout-direccion-nueva">
                                        <div className="checkout-fila">
                                            <div className="checkout-campo checkout-campo--ancho">
                                                <label htmlFor="checkout-calle">Calle</label>
                                                <input id="checkout-calle" maxLength={255} type="text" value={calle} onChange={(e) => setCalle(e.target.value)} required={!direccionOpcional} placeholder="Ej: Av. Providencia" />
                                            </div>
                                            <div className="checkout-campo">
                                                <label htmlFor="checkout-numero">Número</label>
                                                <input id="checkout-numero" maxLength={50} type="text" value={numero} onChange={(e) => setNumero(e.target.value)} required={!direccionOpcional} />
                                            </div>
                                        </div>
                                        <div className="checkout-campo">
                                            <label htmlFor="checkout-dpto">Dpto, Casa o Referencia (Opcional)</label>
                                            <input id="checkout-dpto" maxLength={100} type="text" value={dptoCasa} onChange={(e) => setDptoCasa(e.target.value)} placeholder="Ej: Depto 505" />
                                        </div>
                                        <div className="checkout-fila">
                                            <div className="checkout-campo">
                                                <label htmlFor="checkout-comuna">Comuna</label>
                                                {hayCouriers ? (
                                                    <select id="checkout-comuna" value={comuna} onChange={(e) => { setComuna(e.target.value); setMensaje(''); }} required={!direccionOpcional} disabled={cargandoComunas}>
                                                        <option value="">{cargandoComunas ? "Cargando..." : "-- Selecciona --"}</option>
                                                        {listaComunas.map(c => <option key={c} value={c}>{c}</option>)}
                                                    </select>
                                                ) : (
                                                    <input id="checkout-comuna" maxLength={100} type="text" autoComplete="address-level2" value={comuna} onChange={(e) => setComuna(e.target.value)} required={!direccionOpcional} placeholder="Ej: Ñuñoa" />
                                                )}
                                            </div>
                                            <div className="checkout-campo">
                                                <label htmlFor="checkout-ciudad">Ciudad</label>
                                                <input id="checkout-ciudad" maxLength={100} type="text" value={ciudad} onChange={(e) => setCiudad(e.target.value)} required={!direccionOpcional} />
                                            </div>
                                        </div>
                                        {usuarioAutenticado && (
                                            <label className="checkout-casilla">
                                                <input type="checkbox" checked={guardarNuevaDireccion} onChange={(e) => setGuardarNuevaDireccion(e.target.checked)} />
                                                Guardar esta dirección para mis próximas compras
                                            </label>
                                        )}
                                    </div>
                                )}
                            </div>
                        ) : tipoDespacho === 'SUCURSAL' ? (
                            <div className="checkout-entrega">
                                {couriersConSucursal.length > 1 && (
                                    <div className="checkout-campo">
                                        <label htmlFor="checkout-courier-sucursal">¿En qué courier retiras?</label>
                                        <select id="checkout-courier-sucursal" value={courierSucursal?.codigo || ''} onChange={(e) => { setCodigoCourierSucursal(e.target.value); setSucursalElegida(null); setMensaje(''); }}>
                                            {couriersConSucursal.map(courier => <option key={courier.codigo} value={courier.codigo}>{courier.nombre}</option>)}
                                        </select>
                                    </div>
                                )}
                                <div className="checkout-campo">
                                    <label htmlFor="checkout-comuna-sucursal">¿En qué comuna te encuentras?</label>
                                    <select id="checkout-comuna-sucursal" value={comunaSucursal} onChange={(e) => { setComunaSucursal(e.target.value); setSucursalElegida(null); setMensaje(''); }} required disabled={cargandoComunas}>
                                        <option value="">-- Selecciona comuna --</option>
                                        {listaComunas.map(c => <option key={c} value={c}>{c}</option>)}
                                    </select>
                                </div>

                                {cargandoSucursales ? (
                                    <p className="checkout-ayuda" role="status">Buscando oficinas disponibles...</p>
                                ) : comunaSucursal && sucursalesDisponibles.length === 0 ? (
                                    <div className="checkout-aviso checkout-aviso--error">
                                        Lo sentimos, {courierSucursal?.nombre} no tiene oficinas disponibles en <strong>{comunaSucursal}</strong>.
                                    </div>
                                ) : sucursalesDisponibles.length > 0 && (
                                    <fieldset className="checkout-grupo checkout-direcciones">
                                        <legend className="checkout-etiqueta">Oficinas disponibles</legend>
                                        {sucursalesDisponibles.map(suc => (
                                            <label key={suc.codigo} className={claseOpcion(sucursalSeleccionada?.codigo === suc.codigo) + ' checkout-opcion--fila'}>
                                                <input type="radio" name="sucursal" value={suc.codigo} checked={sucursalSeleccionada?.codigo === suc.codigo} onChange={() => setSucursalElegida({ ...suc, clave: claveSucursales })} />
                                                <span>
                                                    <strong>{suc.nombre}</strong>
                                                    <span className="checkout-ayuda">{suc.direccion}</span>
                                                </span>
                                            </label>
                                        ))}
                                    </fieldset>
                                )}
                            </div>
                        ) : tipoDespacho === 'RETIRO_LOCAL' ? (
                            <div className="checkout-entrega checkout-retiro">
                                <p className="checkout-etiqueta">Retiro gratuito en local</p>
                                <p className="checkout-ayuda">Puedes retirar tu pedido sin costo en nuestra dirección:</p>
                                <p className="checkout-retiro-direccion">
                                    {configTienda?.calle_origen || 'Av. Principal'} #{configTienda?.numero_origen || '123'} {configTienda?.dpto_casa_origen ? `- ${configTienda.dpto_casa_origen}` : ''}, {configTienda?.comuna_origen || 'Santiago'} ({configTienda?.region_origen || 'Metropolitana'})
                                </p>
                            </div>
                        ) : null}

                        {/* --- COSTO DE LA ENTREGA ELEGIDA (con varios couriers, el comprador elige) --- */}
                        {opcionesEntrega.length > 1 ? (
                            <fieldset className="checkout-grupo checkout-logistica">
                                <legend className="checkout-etiqueta">Elige con quién enviarlo</legend>
                                {opcionesEntrega.map((opcion) => (
                                    <label key={opcion.proveedor} className={claseOpcion(opcionEntregaSeleccionada?.proveedor === opcion.proveedor) + ' checkout-opcion--fila'}>
                                        <input type="radio" name="courier" value={opcion.proveedor} checked={opcionEntregaSeleccionada?.proveedor === opcion.proveedor} onChange={() => setProveedorElegido(opcion.proveedor)} />
                                        <span>
                                            <strong>{opcion.nombre}</strong>
                                            <span className="checkout-ayuda">{opcion.tipo === 'RETIRO' ? 'Retiro en Sucursal' : 'Despacho a Domicilio'}</span>
                                        </span>
                                        <strong className="checkout-opcion-precio">{formatoPesos(opcion.costo_envio)}</strong>
                                    </label>
                                ))}
                            </fieldset>
                        ) : opcionesEntrega.length > 0 && (
                            <div className="checkout-logistica">
                                {opcionesEntrega.map((opcion) => (
                                    <div key={opcion.proveedor} className="checkout-logistica-opcion">
                                        <div>
                                            <strong>{opcion.nombre}</strong>
                                            <div className="checkout-ayuda">
                                                {opcion.tipo === 'COORDINADA' ? 'Acordamos contigo el día y el lugar'
                                                    : opcion.tipo === 'RETIRO' ? (tipoDespacho === 'RETIRO_LOCAL' ? 'Retiro en Local Propio' : 'Retiro en Sucursal') : 'Despacho a Domicilio'}
                                            </div>
                                        </div>
                                        <strong>{formatoPesos(opcion.costo_envio)}</strong>
                                    </div>
                                ))}
                            </div>
                        )}
                    </fieldset>
                </form>

                <aside className="checkout-resumen" aria-labelledby="checkout-resumen-titulo">
                    <h2 id="checkout-resumen-titulo" className="checkout-paso">Resumen del pedido</h2>
                    <div className="checkout-resumen-lineas">
                        {itemsCarrito.length > 0 ? itemsCarrito.map((item) => (
                            <div className="checkout-resumen-linea" key={`${item.id}|${item.sku}`}>
                                <span>{`${item.nombre} (x${item.cantidad})`}</span><span>{`$${(item.precio * item.cantidad).toLocaleString('es-CL')}`}</span>
                            </div>
                        )) : <p>No hay productos</p>}
                    </div>

                    <div className="checkout-cupon">
                        <input
                            className="input-cupon"
                            type="text"
                            placeholder="Cupón de descuento"
                            aria-label="Cupón de descuento"
                            value={codigoInput}
                            onChange={(e) => setCodigoInput(e.target.value.toUpperCase())}
                        />
                        <button type="button" className="boton-edicion checkout-cupon-boton" onClick={aplicarCodigo}>
                            Aplicar
                        </button>
                    </div>

                    <div className="checkout-totales">
                        <div className="checkout-total-linea"><span>Subtotal:</span><span>{`$${subtotal.toLocaleString('es-CL')}`}</span></div>

                        {montoDescontado > 0 && (
                            <div className="checkout-total-linea checkout-total-linea--descuento">
                                {/* Un automático no muestra su código: no se escribe y no debe circular */}
                                <span>Descuento {descuentoElegido?.codigo ? `(${descuentoElegido.codigo})` : '(automático)'}:</span>
                                <span>-${Math.round(montoDescontado).toLocaleString('es-CL')}</span>
                            </div>
                        )}

                        {montoSuscriptor > 0 && (
                            <div className="checkout-total-linea checkout-total-linea--descuento">
                                <span>Descuento de suscriptor ({beneficios.descuento}%):</span>
                                <span>-${montoSuscriptor.toLocaleString('es-CL')}</span>
                            </div>
                        )}

                        <div className="checkout-total-linea">
                            <span>Costo de envío:</span>
                            <span>
                                {cotizando ? 'Calculando...' : tieneEnvioGratis ? (
                                    <>
                                        {costoEnvio > 0 && (
                                            <del className="checkout-precio-anterior">
                                                {`$${costoEnvio.toLocaleString('es-CL')}`}
                                            </del>
                                        )}
                                        <span className="checkout-envio-gratis">
                                            {envioGratisSuscriptor && !tieneEnvioGratisCupon ? '$0 (Envío gratis por tu suscripción)' : '$0 (Envío gratis)'}
                                        </span>
                                    </>
                                ) : `$${costoEnvio.toLocaleString('es-CL')}`}
                            </span>
                        </div>

                        <div className="checkout-total-linea checkout-total-linea--final"><span>Total a pagar:</span><span>{`$${totalFinal.toLocaleString('es-CL')}`}</span></div>
                        {proximoAutomatico && subtotal > 0 && (
                            <p className="checkout-ayuda" role="status">
                                Agrega ${(Number(proximoAutomatico.monto_minimo) - subtotal).toLocaleString('es-CL')} más y obtén{' '}
                                {proximoAutomatico.tipo_descuento === 'PORCENTAJE'
                                    ? `un ${Number(proximoAutomatico.valor_descuento)}% de descuento`
                                    : `$${Number(proximoAutomatico.valor_descuento).toLocaleString('es-CL')} de descuento`}.
                            </p>
                        )}
                    </div>

                    {/* RF-04.4: sin aceptar los términos no se puede pagar (el backend también lo valida) */}
                    <label className="checkout-casilla checkout-terminos">
                        <input id="checkout-terminos" type="checkbox" checked={aceptaTerminos} onChange={(e) => setAceptaTerminos(e.target.checked)} required />
                        <span>Acepto los {enlaceLegal('TERMINOS', 'Términos y Condiciones')} y la {enlaceLegal('PRIVACIDAD', 'Política de Privacidad')}.</span>
                    </label>

                    {intentoPagar && faltantes.length > 0 && (
                        <div id="checkout-faltantes" role="alert" className="checkout-aviso checkout-aviso--error checkout-faltantes">
                            <strong>Para pagar, completa:</strong>
                            <ul>{faltantes.map(f => <li key={f.texto}>{f.texto}</li>)}</ul>
                        </div>
                    )}

                    <div className="checkout-pagos">
                        {cargandoPagos ? (
                            <Cargando texto="Cargando métodos de pago...">
                                <div className="esqueleto-pagos">
                                    <Bloque alto="3.2rem" forma="boton" />
                                    <Bloque alto="3.2rem" forma="boton" />
                                </div>
                            </Cargando>
                        ) : pasarelas.length === 0 ? (
                            <p className="checkout-aviso checkout-aviso--error">No hay métodos de pago configurados en la tienda.</p>
                        ) : (
                            pasarelas.map(pasarela => (
                                // Se deshabilita solo mientras procesa o cotiza: con datos faltantes el clic avisa qué falta
                                <button
                                        key={pasarela} type="button" onClick={() => intentarPagar(pasarela)}
                                        disabled={procesandoPago || cotizando || Boolean(esperandoPago)}
                                        aria-disabled={faltantes.length > 0 || undefined}
                                        aria-describedby={intentoPagar && faltantes.length > 0 ? 'checkout-faltantes' : undefined}
                                        className="boton boton-primario checkout-pagar"
                                    >
                                        {procesandoPago ? <Spinner /> : <LogoMedioPago codigo={pasarela} />}
                                        {procesandoPago ? 'Procesando pedido...' : `Pagar con ${NOMBRES_MEDIO_PAGO[pasarela] || pasarela}`}
                                    </button>
                            ))
                        )}
                    </div>
                </aside>
            </div>

            {esperandoPago && !mostrarDialogoPago && (
                <div className="checkout-aviso" role="status">
                    El pago de la orden #{esperandoPago.ordenId} sigue pendiente. Cerrar el aviso no cancela el pedido.
                    <button ref={botonReabrirPago} type="button" className="boton boton-contorno" onClick={() => setMostrarDialogoPago(true)}>Volver a ver el pago pendiente</button>
                </div>
            )}
            {esperandoPago && mostrarDialogoPago && (
                    <Dialogo className="checkout-modal" tituloId="checkout-modal-titulo" onCerrar={cerrarAvisoPago}>
                        <span className="antetitulo">Pago en curso</span>
                        <h2 id="checkout-modal-titulo" tabIndex={-1} data-foco-inicial>Completando pago en Mercado Pago</h2>
                        <p className="texto-secundario">
                            Se abrió la ventana de Mercado Pago para la <strong>Orden #{esperandoPago.ordenId}</strong>.
                            Completa tu pago allá. Esta pantalla detectará tu pago automáticamente tan pronto como se acredite.
                        </p>
                        <div className="checkout-modal-acciones">
                            <button
                                type="button"
                                className="boton boton-primario"
                                onClick={() => verificarEstadoOrden(esperandoPago.ordenId)}
                                disabled={verificando}
                            >
                                {verificando && <Spinner />}{verificando ? 'Consultando a Mercado Pago...' : 'Ya pagué (Verificar mi pago)'}
                            </button>
                            <a href={esperandoPago.urlPago} target="_blank" rel="noopener noreferrer" className="checkout-modal-enlace">
                                ¿Se cerró la ventana? Abrir Mercado Pago de nuevo
                            </a>
                            <button
                                type="button"
                                className="boton-texto"
                                onClick={cerrarAvisoPago}
                            >
                                Cerrar y volver al checkout
                            </button>
                        </div>
                    </Dialogo>
            )}
        </div>
    );
}
