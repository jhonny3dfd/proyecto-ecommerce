import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock('../hooks/useConfiguracionTienda', () => ({ default: () => ({ nombre_tienda: 'Tienda QA' }) }));
vi.mock('../components/header/header', () => ({ default: () => null }));

import clienteAxios from '../components/auth/axiosConfig';
import Resena from '../pages/Resena';
import { guardarTokensDeEnlace, leerTokensDeEnlace, olvidarTokensDeEnlace } from '../utils/enlacesConToken';

const FORMULARIO = {
  orden_id: 12, nombre_sugerido: 'Ana P.',
  productos: [{ producto_id: 'taza', nombre: 'Taza de cerámica' }, { producto_id: 'plato', nombre: 'Plato hondo' }]
};

function renderResena(ruta = '/resena?t=token-firmado') {
  return render(<MemoryRouter initialEntries={[ruta]}><Resena /></MemoryRouter>);
}

const grupo = (nombre) => screen.getByRole('group', { name: nombre });
const elegir = (nombreGrupo, estrellas) => fireEvent.click(
  within(grupo(nombreGrupo)).getByRole('radio', { name: new RegExp(`^${estrellas} estrellas?:`) }));
const aceptar = () => fireEvent.click(screen.getByRole('checkbox', { name: /acepto que mi reseña/i }));
const enviar = () => fireEvent.click(screen.getByRole('button', { name: 'Enviar reseña' }));

describe('Formulario de reseña', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clienteAxios.get.mockResolvedValue({ data: FORMULARIO });
    clienteAxios.post.mockResolvedValue({ data: { mensaje: '¡Gracias por tu reseña! La tienda la revisará.' } });
  });

  afterEach(() => {
    cleanup();
    olvidarTokensDeEnlace('/resena');
  });

  it('abre el pedido del enlace con sus productos y el nombre sugerido', async () => {
    renderResena();

    expect(await screen.findByText('Pedido #12')).toBeInTheDocument();
    expect(clienteAxios.get).toHaveBeenCalledWith('ventas/resenas/formulario/', { params: { t: 'token-firmado' } });
    expect(screen.getByLabelText('Nombre a mostrar')).toHaveValue('Ana P.');
    expect(grupo('Taza de cerámica')).toBeInTheDocument();
    expect(grupo('Plato hondo')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /acepto que mi reseña/i })).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Enviar reseña' })).toBeDisabled();
  });

  it('las estrellas son un grupo de radios con nombre, obligatorio para la tienda', async () => {
    renderResena();

    const tienda = await screen.findByRole('group', { name: '¿Cómo calificarías a Tienda QA?' });
    const radios = within(tienda).getAllByRole('radio');
    expect(radios.map(r => r.getAttribute('aria-label') || r.labels[0].textContent)).toEqual([
      '1 estrella: Muy mala', '2 estrellas: Mala', '3 estrellas: Regular', '4 estrellas: Buena', '5 estrellas: Excelente'
    ]);
    radios.forEach(radio => expect(radio).toBeRequired());
    expect(within(grupo('Taza de cerámica')).getAllByRole('radio')[0]).not.toBeRequired();

    elegir('¿Cómo calificarías a Tienda QA?', 4);
    expect(within(tienda).getByRole('radio', { name: '4 estrellas: Buena' })).toBeChecked();
  });

  it('sin estrellas para la tienda no envía y lo avisa en el grupo', async () => {
    renderResena();
    await screen.findByText('Pedido #12');
    aceptar();
    enviar();

    expect(await screen.findByText('Elige cuántas estrellas le das a Tienda QA.')).toBeInTheDocument();
    expect(clienteAxios.post).not.toHaveBeenCalled();
    expect(within(grupo('¿Cómo calificarías a Tienda QA?')).getAllByRole('radio')[0]).toHaveAttribute('aria-invalid', 'true');
  });

  it('envía la tienda y solo los productos calificados, y agradece', async () => {
    renderResena();
    await screen.findByText('Pedido #12');
    elegir('¿Cómo calificarías a Tienda QA?', 5);
    fireEvent.change(screen.getByLabelText('Comentario (opcional)'), { target: { value: 'Muy buena atención' } });
    elegir('Taza de cerámica', 4);
    fireEvent.change(screen.getByLabelText('Comentario sobre Taza de cerámica (opcional)'), { target: { value: 'Linda' } });
    // Calificó el plato y se arrepintió
    elegir('Plato hondo', 2);
    fireEvent.click(screen.getByRole('button', { name: 'Quitar la calificación de Plato hondo' }));
    fireEvent.change(screen.getByLabelText('Nombre a mostrar'), { target: { value: 'Ana' } });
    aceptar();
    enviar();

    expect(await screen.findByRole('status')).toHaveTextContent('¡Gracias por tu reseña!');
    expect(clienteAxios.post).toHaveBeenCalledWith('ventas/resenas/', {
      token: 'token-firmado', estrellas: 5, comentario: 'Muy buena atención', nombre_publico: 'Ana',
      acepta_publicacion: true, productos: [{ producto_id: 'taza', estrellas: 4, comentario: 'Linda' }]
    });
    expect(screen.queryByRole('button', { name: 'Enviar reseña' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Volver a la tienda' })).toBeInTheDocument();
  });

  it('usa el token que se guardó fuera de la URL y lo olvida al enviar', async () => {
    guardarTokensDeEnlace('/resena', { t: 'token-guardado' });
    renderResena('/resena');

    await screen.findByText('Pedido #12');
    expect(clienteAxios.get).toHaveBeenCalledWith('ventas/resenas/formulario/', { params: { t: 'token-guardado' } });
    elegir('¿Cómo calificarías a Tienda QA?', 5);
    aceptar();
    enviar();

    expect(await screen.findByRole('status')).toHaveTextContent('¡Gracias por tu reseña!');
    expect(clienteAxios.post.mock.calls[0][1].token).toBe('token-guardado');
    expect(leerTokensDeEnlace('/resena')).toBeNull();
  });

  it('muestra los errores del servidor en su campo y en su producto', async () => {
    clienteAxios.post.mockRejectedValue({ response: { status: 400, data: {
      nombre_publico: ['Usa tu nombre, no tu correo.'], productos: { taza: 'Para comentar un producto, califícalo.' }
    } } });
    renderResena();
    await screen.findByText('Pedido #12');
    elegir('¿Cómo calificarías a Tienda QA?', 3);
    aceptar();
    enviar();

    expect(await screen.findByText('Usa tu nombre, no tu correo.')).toBeInTheDocument();
    expect(screen.getByLabelText('Nombre a mostrar')).toHaveAttribute('aria-invalid', 'true');
    expect(within(grupo('Taza de cerámica')).getByText('Para comentar un producto, califícalo.')).toBeInTheDocument();
  });

  it('un enlace vencido, alterado o ya usado muestra el motivo sin formulario', async () => {
    clienteAxios.get.mockRejectedValue({ response: { status: 409, data: {
      detail: 'Ya dejaste una reseña para este pedido. ¡Gracias!' } } });
    renderResena();

    expect(await screen.findByText(/Ya dejaste una reseña para este pedido/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Enviar reseña' })).not.toBeInTheDocument();
  });

  it('sin token no consulta al servidor', () => {
    renderResena('/resena');

    expect(screen.getByText(/no es válido o ya venció/)).toBeInTheDocument();
    expect(clienteAxios.get).not.toHaveBeenCalled();
  });
});
