import { useId, useState } from 'react';
import clienteAxios from './axiosConfig';
import { GoogleLogin } from '@react-oauth/google';
import { Link, useNavigate } from 'react-router-dom';
import { guardarCarrito } from '../carrito';
import Spinner from '../carga/Spinner';

// Mensaje según la causa: credenciales incorrectas o la tienda no responde
const mensajeDeError = (error) => {
    if (error.response?.status === 401) return 'Correo o contraseña incorrectos.';
    if (!error.response) return 'No pudimos conectar con la tienda. Revisa tu conexión e inténtalo de nuevo.';
    return 'No pudimos iniciar sesión. Inténtalo de nuevo.';
};

// googleHabilitado: la tienda configuró GOOGLE_CLIENT_ID (RN-04); si no, no se ofrece Google
// aviso: { texto, email } que deja el registro al crear la cuenta
export default function Login({ onSwitchToRegister, googleHabilitado = false, aviso = null }) {
    const navigate = useNavigate();
    // Prefijo único para asociar cada etiqueta con su campo
    const id = useId();
    const [formData, setFormData] = useState({
        email: aviso?.email || '',
        password: ''
    });
    // Los mensajes van en el formulario (no en alert()) para que el lector de pantalla los anuncie
    const [error, setError] = useState('');
    const [enviando, setEnviando] = useState(false);

    const handleChange = (e) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value
        });
    };

    // Función para descargar el carrito guardado en la base de datos de Django al iniciar sesión

    // Combina el carrito de invitada con el carrito guardado en la cuenta
    const sincronizarCarrito = async () => {
        try {
            // 1. Recuperamos el carrito que existía antes de iniciar sesión
            let carritoInvitado = [];

            try {
                const carritoLocal = localStorage.getItem('carrito_local');
                const datosLocales = carritoLocal ? JSON.parse(carritoLocal) : [];
                carritoInvitado = Array.isArray(datosLocales) ? datosLocales : [];
            } catch {
                carritoInvitado = [];
            }

            // 2. Recuperamos el carrito asociado a la cuenta
            const respuesta = await clienteAxios.get('ventas/carrito/');
            const carritoData = Array.isArray(respuesta.data)
                ? respuesta.data
                : (respuesta.data?.items || []);

            const carritoCuenta = carritoData.map(item => ({
                ...item,
                id: item.producto_mongo_id || item.producto_id || item.id,
                sku: item.variante_sku || item.sku || item.id,
                nombre: item.nombre || item.producto_nombre || item.nombre_producto_snapshot || 'Producto',
                precio: Number(item.precio ?? item.precio_unitario_snapshot ?? 0),
                cantidad: Number(item.cantidad) || 1
            }));

            // 3. Partimos con los productos que ya tenía la cuenta
            const carritoCombinado = carritoCuenta.map(item => ({ ...item }));

            // 4. Agregamos los productos de invitada sin perder cantidades
            carritoInvitado.forEach(item => {
                const id = item.id || item.producto_mongo_id || item.producto_id;
                const sku = item.sku || item.variante_sku || id;

                const existente = carritoCombinado.find(actual =>
                    String(actual.id) === String(id) &&
                    String(actual.sku) === String(sku)
                );

                if (existente) {
                    existente.cantidad =
                        Number(existente.cantidad || 0) + Number(item.cantidad || 1);
                } else {
                    carritoCombinado.push({
                        ...item,
                        id,
                        sku,
                        cantidad: Number(item.cantidad) || 1
                    });
                }
            });

            // 5. Guardamos el carrito combinado en el navegador y en Django
            await guardarCarrito(carritoCombinado);
        } catch (error) {
            console.error('No se pudo sincronizar el carrito al iniciar sesión:', error);
        }
    };


    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setEnviando(true);
        try {
            // 1. Obtenemos los tokens y el interceptor los guarda
            await clienteAxios.post('usuarios/token/', formData);
            
            // 2. Consultamos el rol del usuario
            const respuestaPerfil = await clienteAxios.get('usuarios/me/');
            const rolUsuario = respuestaPerfil.data.rol;

            // 3. Descargamos el carrito asociado a este usuario desde Django
            await sincronizarCarrito();

            const urlAnterior = localStorage.getItem('url_anterior_login');
            if (urlAnterior) {
                localStorage.removeItem('url_anterior_login');
                navigate(urlAnterior);
            } else if (rolUsuario === 'ADMIN') {
                navigate('/admin');
            } else {
                navigate('/catalogo');
            }

        } catch (error) {
            console.error("Axios interceptó un error:", error);
            setError(mensajeDeError(error));
            setEnviando(false);
        }
    };

    const handleGoogleSuccess = async (credentialResponse) => {
        const googleToken = credentialResponse.credential;
        setError('');

        try {
            const { data } = await clienteAxios.post('usuarios/google/', { id_token: googleToken });
            // Este endpoint devuelve los JWT dentro de "tokens" (el interceptor solo guarda los del nivel superior)
            localStorage.setItem('access_token', data.tokens.access);
            localStorage.setItem('refresh_token', data.tokens.refresh);

            const respuestaPerfil = await clienteAxios.get('usuarios/me/');
            const rolUsuario = respuestaPerfil.data.rol;

            // Descargamos el carrito también para Google
            await sincronizarCarrito();

            // Igual que el login con contraseña: vuelve a donde estaba (ej. el checkout)
            const urlAnterior = localStorage.getItem('url_anterior_login');
            if (urlAnterior) {
                localStorage.removeItem('url_anterior_login');
                navigate(urlAnterior);
            } else if (rolUsuario === 'ADMIN') {
                navigate('/admin');
            } else {
                navigate('/catalogo');
            }
        } catch (error) {
            console.error("Axios interceptó un error con Google:", error);
            setError('No se pudo completar el acceso con Google.');
        }
    };

    const handleGoogleError = () => {
        console.error("Error al iniciar sesión con Google");
        setError('No se pudo completar el acceso con Google.');
    };

    // Las credenciales no se distinguen por campo: el error describe a los dos
    const camposConError = error
        ? { 'aria-invalid': true, 'aria-describedby': `${id}-error` }
        : {};

    return (
        <div className="auth-tarjeta">
            <span className="antetitulo">Mi cuenta</span>
            <h1 className="auth-titulo">Iniciar sesión</h1>

            {aviso && !error && <p role="status" className="auth-aviso auth-aviso--exito">{aviso.texto}</p>}
            {error && <p id={`${id}-error`} role="alert" className="auth-aviso auth-aviso--error">{error}</p>}

            <form onSubmit={handleSubmit} className="auth-formulario">
                <div className="auth-campo">
                    <label htmlFor={`${id}-email`}>Correo electrónico</label>
                    <input
                        id={`${id}-email`}
                        type="email"
                        name="email"
                        autoComplete="email"
                        value={formData.email}
                        onChange={handleChange}
                        required
                        {...camposConError}
                    />
                </div>
                <div className="auth-campo">
                    <label htmlFor={`${id}-password`}>Contraseña</label>
                    <input
                        id={`${id}-password`}
                        type="password"
                        name="password"
                        autoComplete="current-password"
                        value={formData.password}
                        onChange={handleChange}
                        required
                        {...camposConError}
                    />
                </div>
                <Link to="/recuperar-contrasena" className="auth-olvido">¿Olvidaste tu contraseña?</Link>
                <button type="submit" className="boton boton-primario auth-enviar" disabled={enviando}>
                    {enviando && <Spinner />}{enviando ? 'Entrando...' : 'Entrar'}
                </button>
            </form>

            {googleHabilitado && (
                <>
                    <p className="auth-separador"><span>O ingresa con</span></p>

                    <div className="auth-google">
                        <GoogleLogin
                            onSuccess={handleGoogleSuccess}
                            onError={handleGoogleError}
                        />
                    </div>
                </>
            )}

            <p className="auth-cambiar">
                ¿No tienes cuenta?{' '}
                <button type="button" className="boton-texto auth-cambiar-boton" onClick={onSwitchToRegister}>
                    Regístrate aquí
                </button>
            </p>
        </div>
    );
}
