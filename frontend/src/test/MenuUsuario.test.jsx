
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import MenuUsuario from '../components/MenuUsuario';
import clienteAxios from '../components/auth/axiosConfig';

vi.mock('../components/auth/axiosConfig', () => ({
  default: {
    get: vi.fn(),
  },
}));

const renderMenu = () => render(
    <MemoryRouter initialEntries={['/otra-ruta']}>
        <Routes>
            <Route path="/otra-ruta" element={<MenuUsuario />} />
            <Route path="/" element={<h1>Inicio de tienda</h1>} />
            <Route path="/mis-pedidos" element={<h1>Mis pedidos</h1>} />
            <Route path="/mis-direcciones" element={<h1>Mis direcciones</h1>} />
            <Route path="/cambiar-contrasena" element={<h1>Cambiar contraseña</h1>} />
        </Routes>
    </MemoryRouter>
);

afterEach(() => {
  cleanup();
});

describe('MenuUsuario', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    clienteAxios.get.mockResolvedValue({
      data: { nombre: 'Javier' },
    });
  });

  it('muestra el enlace de inicio de sesión cuando no existe token', () => {
    renderMenu();

    expect(screen.getByRole('link', { name: 'Iniciar sesión' }),).toHaveAttribute('href', '/login');
    expect(clienteAxios.get).not.toHaveBeenCalled();
  });

  it('consulta el perfil cuando existe una sesión', async () => {
    localStorage.setItem('access_token', 'token-prueba');
    renderMenu();

    await waitFor(() => {expect(clienteAxios.get).toHaveBeenCalledWith('usuarios/me/');});
    fireEvent.click(await screen.findByRole('button', { name: 'Menú de usuario: Hola, Javier' }));
    expect(screen.queryByRole('link', { name: 'Mi cumpleaños' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Mis suscripciones' })).not.toBeInTheDocument();
  });

  it('muestra el nombre recibido del backend', async () => {
    localStorage.setItem('access_token', 'token-prueba');
    renderMenu();

    expect(await screen.findByRole('button', {name: 'Menú de usuario: Hola, Javier',}),).toBeInTheDocument();
  });

  it('mantiene el nombre predeterminado si el backend no devuelve nombre', async () => {
    localStorage.setItem('access_token', 'token-prueba');
    clienteAxios.get.mockResolvedValue({ data: {} });
    renderMenu();

    expect(await screen.findByRole('button', {name: 'Menú de usuario: Hola, Usuario',}),).toBeInTheDocument();
  });

  it('abre el menú y muestra sus opciones', async () => {
    localStorage.setItem('access_token', 'token-prueba');
    renderMenu();

    const boton = await screen.findByRole('button', {name: 'Menú de usuario: Hola, Javier',});

    fireEvent.click(boton);

    expect(boton).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Bienvenido de nuevo,')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Mis pedidos' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Mis direcciones de envío' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Cambiar contraseña' })).toBeInTheDocument();
  });

  it('cierra el menú al presionar Escape y devuelve el foco al botón', async () => {
    localStorage.setItem('access_token', 'token-prueba');
    renderMenu();

    const boton = await screen.findByRole('button', {name: 'Menú de usuario: Hola, Javier',});

    fireEvent.click(boton);
    fireEvent.keyDown(boton.parentElement, { key: 'Escape' });

    expect(boton).toHaveAttribute('aria-expanded', 'false');
    expect(boton).toHaveFocus();
  });

  it('cierra el menú al hacer clic fuera de él', async () => {
    localStorage.setItem('access_token', 'token-prueba');
    renderMenu();

    const boton = await screen.findByRole('button', {name: 'Menú de usuario: Hola, Javier',});

    fireEvent.click(boton);
    expect(screen.getByRole('link', { name: 'Mis pedidos' })).toBeInTheDocument();

    fireEvent.mouseDown(document.body);

    expect(screen.queryByRole('link', { name: 'Mis pedidos' })).not.toBeInTheDocument();
  });

  it('cierra sesión y elimina los datos almacenados', async () => {
    localStorage.setItem('access_token', 'access');
    localStorage.setItem('refresh_token', 'refresh');
    localStorage.setItem('rol', 'cliente');
    localStorage.setItem('carrito_local', '[]');

    const eventoCarrito = vi.fn();
    window.addEventListener('carritoActualizado', eventoCarrito);
    renderMenu();

    const botonMenu = await screen.findByRole('button', {name: 'Menú de usuario: Hola, Javier',});

    fireEvent.click(botonMenu);
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }));

    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
    expect(localStorage.getItem('rol')).toBeNull();
    expect(localStorage.getItem('carrito_local')).toBeNull();
    expect(eventoCarrito).toHaveBeenCalledTimes(1);

    expect(await screen.findByRole('heading', {name: 'Inicio de tienda',})).toBeInTheDocument();
    window.removeEventListener('carritoActualizado', eventoCarrito);
  });
});
