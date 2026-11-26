import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock('../hooks/useConfiguracionTienda', () => ({ default: () => ({ nombre_tienda: 'Tienda QA' }) }));
vi.mock('../components/header/header', () => ({ default: () => null }));

import clienteAxios from '../components/auth/axiosConfig';
import CambiarContrasena from '../pages/CambiarContrasena';

const NUEVA = 'Otra-Clave-Segura-2026';

function abrir(tieneContrasena = true) {
  clienteAxios.get.mockResolvedValue({ data: { nombre: 'Ana', rol: 'COMPRADOR', tiene_contrasena: tieneContrasena } });
  render(<MemoryRouter><CambiarContrasena /></MemoryRouter>);
}

function escribir({ actual, password = NUEVA, password2 = password }) {
  if (actual !== undefined) fireEvent.change(screen.getByLabelText('Contraseña actual'), { target: { value: actual } });
  fireEvent.change(screen.getByLabelText('Nueva contraseña'), { target: { value: password } });
  fireEvent.change(screen.getByLabelText('Repite la nueva contraseña'), { target: { value: password2 } });
  fireEvent.click(screen.getByRole('button', { name: 'Guardar contraseña' }));
}

describe('Cambiar contraseña', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it('pide la actual y la nueva, y confirma el cambio dejando el formulario vacío', async () => {
    clienteAxios.post.mockResolvedValue({ data: {} });
    abrir();
    expect(await screen.findByRole('heading', { name: 'Cambiar contraseña' })).toBeInTheDocument();
    escribir({ actual: 'Clave-Antigua-2025' });

    expect(await screen.findByText('Tu contraseña se cambió.')).toHaveAttribute('role', 'status');
    expect(clienteAxios.post).toHaveBeenCalledWith('usuarios/contrasena/cambiar/',
      { actual: 'Clave-Antigua-2025', password: NUEVA, password2: NUEVA });
    expect(screen.getByLabelText('Contraseña actual')).toHaveValue('');
    expect(screen.getByLabelText('Nueva contraseña')).toHaveValue('');
  });

  it('muestra el error de la contraseña actual en su campo', async () => {
    clienteAxios.post.mockRejectedValue({
      response: { status: 400, data: { actual: ['La contraseña actual no es correcta.'] } },
    });
    abrir();
    await screen.findByLabelText('Contraseña actual');
    escribir({ actual: 'equivocada' });

    expect(await screen.findByText('La contraseña actual no es correcta.')).toBeInTheDocument();
    expect(screen.getByLabelText('Contraseña actual')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText('Contraseña actual')).toHaveAccessibleDescription('La contraseña actual no es correcta.');
  });

  it('si las nuevas no coinciden avisa sin llamar a la tienda', async () => {
    abrir();
    await screen.findByLabelText('Contraseña actual');
    escribir({ actual: 'Clave-Antigua-2025', password2: 'otra' });

    expect(screen.getByText('Las contraseñas no coinciden.')).toBeInTheDocument();
    expect(clienteAxios.post).not.toHaveBeenCalled();
  });

  it('una cuenta de Google crea su contraseña sin escribir la actual', async () => {
    clienteAxios.post.mockResolvedValue({ data: {} });
    abrir(false);

    expect(await screen.findByRole('heading', { name: 'Crear contraseña' })).toBeInTheDocument();
    expect(screen.getByText(/Hoy entras con Google/)).toBeInTheDocument();
    expect(screen.queryByLabelText('Contraseña actual')).not.toBeInTheDocument();
    escribir({});

    expect(await screen.findByText(/Tu contraseña quedó creada/)).toBeInTheDocument();
    expect(clienteAxios.post).toHaveBeenCalledWith('usuarios/contrasena/cambiar/',
      { actual: '', password: NUEVA, password2: NUEVA });
    // Desde ahora tiene contraseña: un segundo cambio ya pide la actual
    expect(screen.getByLabelText('Contraseña actual')).toBeInTheDocument();
  });

  it('ofrece recuperarla por correo si no recuerda la actual', async () => {
    abrir();
    expect(await screen.findByRole('link', { name: 'Recupérala por correo' }))
      .toHaveAttribute('href', '/recuperar-contrasena');
  });

  it('avisa si no pudo cargar la cuenta', async () => {
    clienteAxios.get.mockRejectedValue(new Error('Network Error'));
    render(<MemoryRouter><CambiarContrasena /></MemoryRouter>);

    expect(await screen.findByRole('alert')).toHaveTextContent('No pudimos cargar tu cuenta');
    expect(screen.queryByLabelText('Nueva contraseña')).not.toBeInTheDocument();
  });
});
