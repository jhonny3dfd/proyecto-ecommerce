import { useId, useState } from 'react';
import { Link } from 'react-router-dom';
import clienteAxios from '../components/auth/axiosConfig';
import AuthLayout from '../components/auth/AuthLayout';
import Spinner from '../components/carga/Spinner';

const mensajeDeError = (error) => {
  if (!error.response) return 'No pudimos conectar con la tienda. Revisa tu conexión e inténtalo de nuevo.';
  if (error.response.status === 429) return 'Hiciste muchos intentos seguidos. Espera un rato e inténtalo de nuevo.';
  if (error.response.status === 400) return 'Escribe un correo válido.';
  return 'No pudimos enviar el enlace. Inténtalo de nuevo.';
};

// Pide el enlace para elegir una nueva contraseña. La tienda responde lo mismo exista o no la cuenta
export default function RecuperarContrasena() {
  const id = useId();
  const [email, setEmail] = useState('');
  const [enviado, setEnviado] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setEnviando(true);
    try {
      const { data } = await clienteAxios.post('usuarios/contrasena/olvido/', { email });
      setEnviado(data?.detail || 'Si el correo tiene una cuenta en la tienda, te enviamos un enlace.');
    } catch (err) {
      setError(mensajeDeError(err));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <AuthLayout>
      <div className="auth-tarjeta">
        <span className="antetitulo">Mi cuenta</span>
        <h1 className="auth-titulo">Recuperar contraseña</h1>

        {enviado ? (
          <>
            <p role="status" className="auth-aviso auth-aviso--exito">{enviado}</p>
            <p className="auth-texto">El enlace vence en 1 hora. Si no te llega, puedes pedir otro.</p>
            <button type="button" className="boton boton-contorno auth-enviar" onClick={() => setEnviado('')}>
              Pedir otro enlace
            </button>
          </>
        ) : (
          <>
            <p className="auth-texto">Escribe el correo de tu cuenta y te enviaremos un enlace para elegir una nueva contraseña.</p>
            {error && <p id={`${id}-error`} role="alert" className="auth-aviso auth-aviso--error">{error}</p>}
            <form onSubmit={handleSubmit} className="auth-formulario">
              <div className="auth-campo">
                <label htmlFor={`${id}-email`}>Correo electrónico</label>
                <input
                  id={`${id}-email`}
                  type="email"
                  name="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  {...(error ? { 'aria-invalid': true, 'aria-describedby': `${id}-error` } : {})}
                />
              </div>
              <button type="submit" className="boton boton-primario auth-enviar" disabled={enviando}>
                {enviando && <Spinner />}{enviando ? 'Enviando...' : 'Enviar enlace'}
              </button>
            </form>
          </>
        )}

        <p className="auth-cambiar">
          ¿Te acordaste? <Link to="/login" className="auth-cambiar-boton">Inicia sesión</Link>
        </p>
      </div>
    </AuthLayout>
  );
}
