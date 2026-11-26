import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import clienteAxios from './auth/axiosConfig';

// `suscripciones`: la tienda ofrece suscripciones (pedido de un cliente, opcional); lo indica el header
const MenuUsuario = ({ suscripciones = false }) => {
    const botonRef = useRef(null);
    const [isOpen, setIsOpen] = useState(false);
    const [nombreUsuario, setNombreUsuario] = useState('Usuario');
    const menuRef = useRef(null);
    const navigate = useNavigate();

    const token = localStorage.getItem('access_token');
    const isLoggedIn = !!token;
    
    // Obtenemos el nombre real del usuario autenticado consultando el backend
    useEffect(() => {
        if (isLoggedIn) {
            clienteAxios.get('usuarios/me/')
                .then(({ data }) => {
                    const nombreReal = data.nombre || 'Usuario';
                    setNombreUsuario(nombreReal);
                })
                .catch((error) => {
                    console.error("No se pudo obtener el perfil del usuario:", error);
                });
        }
    }, [isLoggedIn]);

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (menuRef.current && !menuRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const cerrarSesion = () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('rol');
        localStorage.removeItem('carrito_local');
        window.dispatchEvent(new Event('carritoActualizado'));
        setIsOpen(false);
        navigate('/');
    };

    if (!isLoggedIn) {
        return (
            <Link to="/login" className="header-enlace-sesion">
                Iniciar sesión
            </Link>
        );
    }

    return (
        <div className="menu-usuario" ref={menuRef} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setIsOpen(false); }} onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); setIsOpen(false); botonRef.current?.focus(); } }}>
            <button
                ref={botonRef}
                type="button"
                className="header-icono menu-usuario-boton"
                aria-label={`Menú de usuario: Hola, ${nombreUsuario}`}
                aria-expanded={isOpen}
                onClick={() => setIsOpen(!isOpen)}
            >
                <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                    strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="8" r="4" />
                    <path d="M4 21a8 8 0 0 1 16 0" />
                </svg>
                <span className="menu-usuario-saludo">Hola, {nombreUsuario}</span>
            </button>

            {isOpen && (
                <div className="menu-usuario-panel panel-header">
                    <div className="panel-header-encabezado">
                        <p className="texto-secundario">Bienvenido de nuevo,</p>
                        <h3>{nombreUsuario}</h3>
                    </div>

                    <ul className="menu-usuario-enlaces lista-sin-estilo">
                        <li><Link to="/mis-pedidos" onClick={() => setIsOpen(false)}>Mis pedidos</Link></li>
                        {/* Suscripciones (pedido de un cliente, opcional): solo con el módulo activo */}
                        {suscripciones && (
                            <>
                                <li><Link to="/mis-suscripciones" onClick={() => setIsOpen(false)}>Mis suscripciones</Link></li>
                                <li><Link to="/mi-cumpleanos" onClick={() => setIsOpen(false)}>Mi cumpleaños</Link></li>
                            </>
                        )}
                        <li><Link to="/mis-direcciones" onClick={() => setIsOpen(false)}>Mis direcciones de envío</Link></li>
                        <li><Link to="/cambiar-contrasena" onClick={() => setIsOpen(false)}>Cambiar contraseña</Link></li>
                    </ul>

                    <div className="menu-usuario-pie">
                        <button type="button" className="boton-texto" onClick={cerrarSesion}>Cerrar sesión</button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default MenuUsuario;
