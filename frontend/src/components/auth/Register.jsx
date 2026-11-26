import { useId, useState } from 'react';
import clienteAxios from './axiosConfig';
import Spinner from '../carga/Spinner';

const campos = [
    { nombre: 'nombre', etiqueta: 'Nombre', tipo: 'text', autocompletar: 'given-name' },
    { nombre: 'apellido_paterno', etiqueta: 'Apellido paterno', tipo: 'text', autocompletar: 'family-name' },
    { nombre: 'email', etiqueta: 'Correo electrónico', tipo: 'email', autocompletar: 'email' },
    { nombre: 'password', etiqueta: 'Contraseña', tipo: 'password', autocompletar: 'new-password' },
    { nombre: 'password2', etiqueta: 'Confirmar contraseña', tipo: 'password', autocompletar: 'new-password' }
];

const NOMBRES_CAMPOS = campos.map(campo => campo.nombre);

// El backend responde { campo: [mensajes] }: cada mensaje va bajo su campo y el resto, arriba del formulario
const leerErrores = (error) => {
    const data = error.response?.data;
    if (!error.response) {
        return { general: 'No pudimos conectar con la tienda. Revisa tu conexión e inténtalo de nuevo.', campos: {} };
    }
    if (error.response.status !== 400 || !data || typeof data !== 'object') {
        return { general: 'No pudimos crear tu cuenta. Inténtalo de nuevo.', campos: {} };
    }
    const porCampo = {};
    const otros = [];
    Object.entries(data).forEach(([campo, mensajes]) => {
        const texto = [].concat(mensajes).join(' ');
        if (NOMBRES_CAMPOS.includes(campo)) porCampo[campo] = texto;
        else otros.push(texto);
    });
    return {
        general: otros.length ? otros.join(' ') : 'Revisa los datos marcados.',
        campos: porCampo
    };
};

// onSwitchToLogin(aviso): al crear la cuenta se vuelve al login con el aviso y el correo ya escrito
export default function Register({ onSwitchToLogin }) {
    // Prefijo único para asociar cada etiqueta con su campo
    const id = useId();
    const [formData, setFormData] = useState({
        nombre: '',
        apellido_paterno: '',
        email: '',
        password: '',
        password2: ''
    });
    // { general, campos: { nombre_del_campo: mensaje } }
    const [errores, setErrores] = useState({ general: '', campos: {} });
    const [enviando, setEnviando] = useState(false);

    const handleChange = (e) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value
        });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        if (formData.password !== formData.password2) {
            setErrores({ general: 'Revisa los datos marcados.', campos: { password2: 'Las contraseñas no coinciden.' } });
            return;
        }

        setErrores({ general: '', campos: {} });
        setEnviando(true);
        try {
            await clienteAxios.post('/usuarios/registro/', formData);
            onSwitchToLogin({
                texto: 'Tu cuenta quedó creada. Ya puedes iniciar sesión.',
                email: formData.email
            });
        } catch (error) {
            console.error("Error en el registro:", error);
            setErrores(leerErrores(error));
            setEnviando(false);
        }
    };

    return (
        <div className="auth-tarjeta">
            <span className="antetitulo">Mi cuenta</span>
            <h1 className="auth-titulo">Crear cuenta</h1>

            {errores.general && (
                <p role="alert" className="auth-aviso auth-aviso--error">{errores.general}</p>
            )}

            <form onSubmit={handleSubmit} className="auth-formulario">
                {campos.map(campo => {
                    const mensaje = errores.campos[campo.nombre];
                    const idError = `${id}-${campo.nombre}-error`;
                    return (
                        <div className="auth-campo" key={campo.nombre}>
                            <label htmlFor={`${id}-${campo.nombre}`}>{campo.etiqueta}</label>
                            <input
                                id={`${id}-${campo.nombre}`}
                                type={campo.tipo}
                                name={campo.nombre}
                                autoComplete={campo.autocompletar}
                                // El mismo largo que acepta el servidor (nombre, apellido, correo y contraseña)
                                maxLength={campo.tipo === 'password' ? 128 : 255}
                                value={formData[campo.nombre]}
                                onChange={handleChange}
                                required
                                aria-invalid={mensaje ? true : undefined}
                                aria-describedby={mensaje ? idError : undefined}
                            />
                            {mensaje && <p id={idError} className="auth-campo-error">{mensaje}</p>}
                        </div>
                    );
                })}
                <button type="submit" className="boton boton-primario auth-enviar" disabled={enviando}>
                    {enviando && <Spinner />}{enviando ? 'Creando cuenta...' : 'Registrarse'}
                </button>
            </form>

            <p className="auth-cambiar">
                ¿Ya tienes cuenta?{' '}
                <button type="button" className="boton-texto auth-cambiar-boton" onClick={() => onSwitchToLogin()}>
                    Inicia sesión aquí
                </button>
            </p>
        </div>
    );
}
