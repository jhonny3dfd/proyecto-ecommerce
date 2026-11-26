import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import clienteAxios from '../components/auth/axiosConfig';
import AuthLayout from '../components/auth/AuthLayout';
import CamposContrasenaNueva from '../components/auth/CamposContrasenaNueva';
import { leerErroresContrasena } from '../components/auth/erroresContrasena';
import { leerTokensDeEnlace, olvidarTokensDeEnlace } from '../utils/enlacesConToken';
import Spinner from '../components/carga/Spinner';

const RUTA = '/restablecer-contrasena';

// Elige la nueva contraseña con el enlace del correo (main.jsx ya sacó uid y token de la URL)
export default function RestablecerContrasena() {
  const navigate = useNavigate();
  const [enlace] = useState(() => leerTokensDeEnlace(RUTA));
  const [formData, setFormData] = useState({ password: '', password2: '' });
  const [errores, setErrores] = useState({ general: '', campos: {}, enlaceInvalido: !enlace });
  const [enviando, setEnviando] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (formData.password !== formData.password2) {
      setErrores({ general: 'Revisa los datos marcados.', campos: { password2: 'Las contraseñas no coinciden.' } });
      return;
    }
    setErrores({ general: '', campos: {} });
    setEnviando(true);
    try {
      await clienteAxios.post('usuarios/contrasena/restablecer/', { ...enlace, ...formData });
      olvidarTokensDeEnlace(RUTA);
      navigate('/login', { state: { aviso: { texto: 'Tu contraseña se cambió. Ya puedes iniciar sesión.' } } });
    } catch (error) {
      const leidos = leerErroresContrasena(error, ['password', 'password2'],
        'No pudimos cambiar tu contraseña. Inténtalo de nuevo.');
      if (leidos.enlaceInvalido) olvidarTokensDeEnlace(RUTA);
      setErrores(leidos);
      setEnviando(false);
    }
  };

  if (errores.enlaceInvalido) {
    return (
      <AuthLayout>
        <div className="auth-tarjeta">
          <span className="antetitulo">Mi cuenta</span>
          <h1 className="auth-titulo">Nueva contraseña</h1>
          <p role="alert" className="auth-aviso auth-aviso--error">
            El enlace no es válido o ya venció. Los enlaces duran 1 hora y sirven una sola vez.
          </p>
          <Link to="/recuperar-contrasena" className="boton boton-primario auth-enviar">Pedir un enlace nuevo</Link>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <div className="auth-tarjeta">
        <span className="antetitulo">Mi cuenta</span>
        <h1 className="auth-titulo">Nueva contraseña</h1>

        {errores.general && <p role="alert" className="auth-aviso auth-aviso--error">{errores.general}</p>}

        <form onSubmit={handleSubmit} className="auth-formulario">
          <CamposContrasenaNueva
            valores={formData}
            errores={errores.campos}
            onChange={(e) => setFormData({ ...formData, [e.target.name]: e.target.value })}
          />
          <button type="submit" className="boton boton-primario auth-enviar" disabled={enviando}>
            {enviando && <Spinner />}{enviando ? 'Guardando...' : 'Guardar contraseña'}
          </button>
        </form>
      </div>
    </AuthLayout>
  );
}
