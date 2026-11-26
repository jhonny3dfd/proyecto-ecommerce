import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../components/auth/axiosConfig', () => ({ default: { post: vi.fn() } }));
vi.mock('../hooks/useConfiguracionTienda', () => ({ default: () => ({ nombre_tienda: 'Tienda QA' }) }));
vi.mock('../components/header/header', () => ({ default: () => null }));

import clienteAxios from '../components/auth/axiosConfig';
import RecuperarContrasena from '../pages/RecuperarContrasena';

const MENSAJE = 'Si el correo tiene una cuenta en la tienda, te enviamos un enlace para elegir una nueva contraseña.';

function pedirEnlace(email = 'ana@example.test') {
  render(<MemoryRouter><RecuperarContrasena /></MemoryRouter>);
  fireEvent.change(screen.getByLabelText('Correo electrónico'), { target: { value: email } });
  fireEvent.click(screen.getByRole('button', { name: 'Enviar enlace' }));
}

describe('Recuperar contraseña', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it('envía el correo y muestra el mismo aviso que da la tienda, exista o no la cuenta', async () => {
    clienteAxios.post.mockResolvedValue({ data: { detail: MENSAJE } });
    pedirEnlace();

    expect(await screen.findByRole('status')).toHaveTextContent(MENSAJE);
    expect(clienteAxios.post).toHaveBeenCalledWith('usuarios/contrasena/olvido/', { email: 'ana@example.test' });
    expect(screen.queryByLabelText('Correo electrónico')).not.toBeInTheDocument();
  });

  it('se puede pedir otro enlace', async () => {
    clienteAxios.post.mockResolvedValue({ data: { detail: MENSAJE } });
    pedirEnlace();

    fireEvent.click(await screen.findByRole('button', { name: 'Pedir otro enlace' }));
    expect(screen.getByLabelText('Correo electrónico')).toHaveValue('ana@example.test');
  });

  it('avisa si se pidieron demasiados enlaces seguidos', async () => {
    clienteAxios.post.mockRejectedValue({ response: { status: 429, data: {} } });
    pedirEnlace();

    expect(await screen.findByRole('alert')).toHaveTextContent('Hiciste muchos intentos seguidos');
    expect(screen.getByLabelText('Correo electrónico')).toHaveAttribute('aria-invalid', 'true');
  });

  it('avisa si no hay conexión con la tienda', async () => {
    clienteAxios.post.mockRejectedValue(new Error('Network Error'));
    pedirEnlace();

    expect(await screen.findByRole('alert')).toHaveTextContent('No pudimos conectar con la tienda');
  });

  it('enlaza de vuelta al inicio de sesión', () => {
    render(<MemoryRouter><RecuperarContrasena /></MemoryRouter>);
    expect(screen.getByRole('link', { name: 'Inicia sesión' })).toHaveAttribute('href', '/login');
  });
});
