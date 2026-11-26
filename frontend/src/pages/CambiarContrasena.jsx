import { useEffect, useId, useState } from 'react';
import { Link } from 'react-router-dom';
import clienteAxios from '../components/auth/axiosConfig';
import AuthLayout from '../components/auth/AuthLayout';
import CamposContrasenaNueva from '../components/auth/CamposContrasenaNueva';
import { leerErroresContrasena } from '../components/auth/erroresContrasena';
import Spinner from '../components/carga/Spinner';

const VACIO = { actual: '', password: '', password2: '' };

// Con la sesión iniciada. Una cuenta creada con Google todavía no tiene contraseña: la crea sin escribir la actual
export default function CambiarContrasena() {
  const id = useId();
  // null mientras se consulta la cuenta
  const [tieneContrasena, setTieneContrasena] = useState(null);
  const [errorCarga, setErrorCarga] = useState('');
  const [formData, setFormData] = useState(VACIO);
  const [errores, setErrores] = useState({ general: '', campos: {} });
  const [exito, setExito] = useState('');
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    clienteAxios.get('usuarios/me/')
      .then(({ data }) => setTieneContrasena(data.tiene_contrasena !== false))
      .catch(() => setErrorCarga('No pudimos cargar tu cuenta. Recarga la página e inténtalo de nuevo.'));
  }, []);

  const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setExito('');
    if (formData.password !== formData.password2) {
      setErrores({ general: 'Revisa los datos marcados.', campos: { password2: 'Las contraseñas no coinciden.' } });
      return;
    }
    setErrores({ general: '', campos: {} });
    setEnviando(true);
    try {
      await clienteAxios.post('usuarios/contrasena/cambiar/', tieneContrasena ? formData : { ...formData, actual: '' });
      setFormData(VACIO);
      setExito(tieneContrasena ? 'Tu contraseña se cambió.' : 'Tu contraseña quedó creada. Ahora también puedes entrar con ella.');
      setTieneContrasena(true);
    } catch (error) {
      setErrores(leerErroresContrasena(error, ['actual', 'password', 'password2'],
        'No pudimos cambiar tu contraseña. Inténtalo de nuevo.'));
    } finally {
      setEnviando(false);
    }
  };

  const titulo = tieneContrasena === false ? 'Crear contraseña' : 'Cambiar contraseña';
  const errorActual = errores.campos.actual;

  return (
    <AuthLayout>
      <div className="auth-tarjeta">
        <span className="antetitulo">Mi cuenta</span>
        <h1 className="auth-titulo">{titulo}</h1>

        {errorCarga && <p role="alert" className="auth-aviso auth-aviso--error">{errorCarga}</p>}
        {!errorCarga && tieneContrasena === null && <p role="status" className="auth-texto">Cargando tu cuenta...</p>}

        {tieneContrasena !== null && (
          <>
            {tieneContrasena === false && (
              <p className="auth-texto">Hoy entras con Google. Crea una contraseña para entrar también con tu correo.</p>
            )}
            {exito && <p role="status" className="auth-aviso auth-aviso--exito">{exito}</p>}
            {errores.general && <p role="alert" className="auth-aviso auth-aviso--error">{errores.general}</p>}

            <form onSubmit={handleSubmit} className="auth-formulario">
              {tieneContrasena && (
                <div className="auth-campo">
                  <label htmlFor={`${id}-actual`}>Contraseña actual</label>
                  <input
                    id={`${id}-actual`}
                    type="password"
                    name="actual"
                    autoComplete="current-password"
                    value={formData.actual}
                    onChange={handleChange}
                    required
                    aria-invalid={errorActual ? true : undefined}
                    aria-describedby={errorActual ? `${id}-actual-error` : undefined}
                  />
                  {errorActual && <p id={`${id}-actual-error`} className="auth-campo-error">{errorActual}</p>}
                </div>
              )}
              <CamposContrasenaNueva valores={formData} errores={errores.campos} onChange={handleChange} />
              <button type="submit" className="boton boton-primario auth-enviar" disabled={enviando}>
                {enviando && <Spinner />}{enviando ? 'Guardando...' : 'Guardar contraseña'}
              </button>
            </form>

            {tieneContrasena && (
              <p className="auth-cambiar">
                ¿No recuerdas la actual?{' '}
                <Link to="/recuperar-contrasena" className="auth-cambiar-boton">Recupérala por correo</Link>
              </p>
            )}
          </>
        )}
      </div>
    </AuthLayout>
  );
}
