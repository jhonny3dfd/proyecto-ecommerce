import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

vi.mock('../components/auth/axiosConfig', () => ({ default: { post: vi.fn() } }));
vi.mock('../hooks/useConfiguracionTienda', () => ({ default: () => ({ nombre_tienda: 'Tienda QA' }) }));
vi.mock('../components/header/header', () => ({ default: () => null }));

import clienteAxios from '../components/auth/axiosConfig';
import RestablecerContrasena from '../pages/RestablecerContrasena';
import { capturarTokensDeEnlace, leerTokensDeEnlace, olvidarTokensDeEnlace } from '../utils/enlacesConToken';

const RUTA = '/restablecer-contrasena';

const NUEVA = 'Otra-Clave-Segura-2026';

function LoginFalso() {
  const { state } = useLocation();
  return <p>Login: {state?.aviso?.texto}</p>;
}

function abrirConEnlace(uid = 'MQ', token = 'abc-123') {
  window.history.replaceState(null, '', `/restablecer-contrasena?uid=${uid}&token=${token}`);
  capturarTokensDeEnlace();
  render(
    <MemoryRouter initialEntries={['/restablecer-contrasena']}>
      <Routes>
        <Route path="/restablecer-contrasena" element={<RestablecerContrasena />} />
        <Route path="/login" element={<LoginFalso />} />
      </Routes>
    </MemoryRouter>
  );
}

function escribir(password, password2 = password) {
  fireEvent.change(screen.getByLabelText('Nueva contraseña'), { target: { value: password } });
  fireEvent.change(screen.getByLabelText('Repite la nueva contraseña'), { target: { value: password2 } });
  fireEvent.click(screen.getByRole('button', { name: 'Guardar contraseña' }));
}

describe('Nueva contraseña', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => {
    cleanup();
    olvidarTokensDeEnlace(RUTA);
    window.history.replaceState(null, '', '/');
  });

  it('guarda la nueva contraseña con el enlace y vuelve al login con el aviso', async () => {
    clienteAxios.post.mockResolvedValue({ data: {} });
    abrirConEnlace();
    escribir(NUEVA);

    expect(await screen.findByText('Login: Tu contraseña se cambió. Ya puedes iniciar sesión.')).toBeInTheDocument();
    expect(clienteAxios.post).toHaveBeenCalledWith('usuarios/contrasena/restablecer/',
      { uid: 'MQ', token: 'abc-123', password: NUEVA, password2: NUEVA });
    expect(leerTokensDeEnlace(RUTA)).toBeNull();
  });

  it('si las contraseñas no coinciden avisa en el campo sin llamar a la tienda', () => {
    abrirConEnlace();
    escribir(NUEVA, 'otra');

    expect(screen.getByText('Las contraseñas no coinciden.')).toBeInTheDocument();
    expect(screen.getByLabelText('Repite la nueva contraseña')).toHaveAttribute('aria-invalid', 'true');
    expect(clienteAxios.post).not.toHaveBeenCalled();
  });

  it('muestra bajo cada campo los errores de la tienda y la ayuda queda asociada al campo', async () => {
    clienteAxios.post.mockRejectedValue({
      response: { status: 400, data: { password: ['Esta contraseña es demasiado común.'] } },
    });
    abrirConEnlace();
    escribir('password123');

    expect(await screen.findByText('Esta contraseña es demasiado común.')).toBeInTheDocument();
    const campo = screen.getByLabelText('Nueva contraseña');
    expect(campo).toHaveAttribute('aria-invalid', 'true');
    expect(campo).toHaveAccessibleDescription(/Al menos 8 caracteres.*demasiado común/);
  });

  it('un enlace vencido o ya usado ofrece pedir uno nuevo', async () => {
    clienteAxios.post.mockRejectedValue({
      response: { status: 400, data: { enlace: ['El enlace no es válido o ya venció. Pide uno nuevo.'] } },
    });
    abrirConEnlace();
    escribir(NUEVA);

    expect(await screen.findByRole('alert')).toHaveTextContent('El enlace no es válido o ya venció');
    expect(screen.getByRole('link', { name: 'Pedir un enlace nuevo' })).toHaveAttribute('href', '/recuperar-contrasena');
    expect(leerTokensDeEnlace(RUTA)).toBeNull();
  });

  it('sin enlace no muestra el formulario', () => {
    render(<MemoryRouter><RestablecerContrasena /></MemoryRouter>);

    expect(screen.getByRole('alert')).toHaveTextContent('El enlace no es válido o ya venció');
    expect(screen.queryByLabelText('Nueva contraseña')).not.toBeInTheDocument();
  });
});
