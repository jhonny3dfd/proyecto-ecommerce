import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Portada from '../components/landing/Portada';

// SCRUM-194: cada foto del carrusel con sus textos y un botón hacia una página del header
const FOTOS = [
  { id: 1, imagen: '/media/a.webp', orden: 0, antetitulo: 'Hecho a mano', titulo: 'Murales', texto: 'Para tu casa',
    destino: 'CATALOGO' },
  { id: 2, imagen: '/media/b.webp', orden: 1, antetitulo: '', titulo: 'Encargos', texto: '', destino: 'COTIZAR' },
];

const portada = (configuracion) => render(
  <MemoryRouter><Portada configuracion={{ texto_bienvenida: 'Bienvenidos', ...configuracion }} /></MemoryRouter>,
);
const pasar = (ms) => act(() => { vi.advanceTimersByTime(ms); });
const titulo = () => screen.getByRole('heading', { level: 1 }).textContent;
const contenido = () => screen.getByRole('heading', { level: 1 }).parentElement;

describe('Portada con textos y botón por foto', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { cleanup(); vi.useRealTimers(); });

  it('cada foto muestra sus textos y su botón cuando le toca', () => {
    portada({ banners: FOTOS, cotizaciones_activas: true });
    expect(titulo()).toBe('Murales');
    expect(screen.getByText('Hecho a mano')).toBeInTheDocument();
    expect(screen.getByText('Para tu casa')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver catálogo' })).toHaveAttribute('href', '/catalogo');

    pasar(5000);
    expect(titulo()).toBe('Encargos');
    expect(screen.queryByText('Hecho a mano')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver cotizar' })).toHaveAttribute('href', '/cotizar');
  });

  it('el botón toma el nombre de la página en el menú', () => {
    portada({
      banners: [{ ...FOTOS[0], destino: 'BLOG' }, FOTOS[0]], blog_activo: true, blog_nombre: 'Proyectos',
      menu_principal: { nombres: { catalogo: 'Productos' } },
    });
    expect(screen.getByRole('link', { name: 'Ver proyectos' })).toHaveAttribute('href', '/blog');
    pasar(5000);
    expect(screen.getByRole('link', { name: 'Ver productos' })).toHaveAttribute('href', '/catalogo');
  });

  it('si el módulo del destino está apagado, la foto muestra sus textos sin botón', () => {
    portada({ banners: [{ ...FOTOS[1], destino: 'COTIZAR' }, { ...FOTOS[0], destino: 'BLOG' }] });
    expect(titulo()).toBe('Encargos');
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    pasar(5000);
    expect(titulo()).toBe('Murales');
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('se detiene mientras el mouse está sobre los textos o el botón', () => {
    portada({ banners: FOTOS });
    fireEvent.mouseEnter(contenido());
    pasar(15000);
    expect(titulo()).toBe('Murales');
    fireEvent.mouseLeave(contenido());
    pasar(5000);
    expect(titulo()).toBe('Encargos');
  });

  it('se detiene mientras el foco está en el botón', () => {
    portada({ banners: FOTOS });
    const enlace = screen.getByRole('link', { name: 'Ver catálogo' });
    act(() => { enlace.focus(); });
    pasar(15000);
    expect(titulo()).toBe('Murales');
    expect(enlace).toHaveFocus();
    act(() => { enlace.blur(); });
    pasar(5000);
    expect(titulo()).toBe('Encargos');
  });

  it('sin fotos propias, la portada usa los textos generales y el botón al catálogo, como antes', () => {
    portada({ subtitulo_bienvenida: 'Hola', texto_landing: 'Texto de la portada' });
    expect(titulo()).toBe('Bienvenidos');
    expect(screen.getByText('Hola')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver catálogo' })).toHaveAttribute('href', '/catalogo');
  });

  it('con una sola foto la portada queda fija y sin botón de pausa', () => {
    portada({ banners: [FOTOS[1]], cotizaciones_activas: true });
    pasar(20000);
    expect(titulo()).toBe('Encargos');
    expect(screen.queryByRole('button', { name: /pausar carrusel/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Foto siguiente' })).not.toBeInTheDocument();
  });

  // Flechas junto a la pausa: navegan en círculo, reinician el reloj y anuncian la posición
  const tresFotos = [...FOTOS, { ...FOTOS[0], id: 3, titulo: 'Retratos' }];

  it('las flechas recorren las fotos en círculo y anuncian la posición', () => {
    portada({ banners: tresFotos });
    const grupo = screen.getByRole('group', { name: 'Controles del carrusel' });
    fireEvent.click(within(grupo).getByRole('button', { name: 'Foto anterior' }));
    expect(titulo()).toBe('Retratos');
    expect(within(grupo).getByRole('status')).toHaveTextContent('Foto 3 de 3.');
    expect(within(grupo).getByText('3 / 3')).toBeInTheDocument();

    fireEvent.click(within(grupo).getByRole('button', { name: 'Foto siguiente' }));
    expect(titulo()).toBe('Murales');
    expect(within(grupo).getByRole('status')).toHaveTextContent('Foto 1 de 3.');
  });

  // Pedido de Alan: los controles muestran solo íconos SVG, que no cambian a emoji en el celular
  it('la pausa y las flechas muestran solo un ícono, sin texto ni caracteres que se vuelvan emoji', () => {
    portada({ banners: tresFotos });
    const grupo = screen.getByRole('group', { name: 'Controles del carrusel' });
    const pausa = within(grupo).getByRole('button', { name: 'Pausar carrusel' });
    for (const boton of within(grupo).getAllByRole('button')) {
      expect(boton).toHaveTextContent(/^$/);
      expect(boton.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    }
    const iconoPausa = pausa.querySelector('svg').innerHTML;
    fireEvent.click(pausa);
    const reanudar = within(grupo).getByRole('button', { name: 'Reanudar carrusel' });
    expect(reanudar).toHaveTextContent(/^$/);
    expect(reanudar.querySelector('svg').innerHTML).not.toBe(iconoPausa);
  });

  it('al usar una flecha, el reloj vuelve a empezar', () => {
    portada({ banners: tresFotos });
    pasar(4000);
    fireEvent.click(screen.getByRole('button', { name: 'Foto siguiente' }));
    expect(titulo()).toBe('Encargos');
    pasar(4000);
    expect(titulo()).toBe('Encargos');
    pasar(1000);
    expect(titulo()).toBe('Retratos');
  });

  it('se detiene mientras el foco está en las flechas', () => {
    portada({ banners: tresFotos });
    const siguiente = screen.getByRole('button', { name: 'Foto siguiente' });
    act(() => { siguiente.focus(); });
    pasar(15000);
    expect(titulo()).toBe('Murales');
    act(() => { siguiente.blur(); });
    pasar(5000);
    expect(titulo()).toBe('Encargos');
  });
});
