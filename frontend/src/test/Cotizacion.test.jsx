import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const { configuracion } = vi.hoisted(() => ({ configuracion: { actual: null } }));

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));
vi.mock('../hooks/useConfiguracionTienda', () => ({
  default: () => configuracion.actual,
  recargarConfiguracion: vi.fn()
}));

import clienteAxios from '../components/auth/axiosConfig';
import Cotizacion from '../pages/Cotizacion';
import GestorCotizaciones from '../components/GestorCotizaciones';

const PRODUCTOS = [
  { id: 'taza', nombre: 'Taza de cerámica', activo: true, publicado: true },
  { id: 'borrador', nombre: 'Producto en borrador', activo: true, publicado: false }
];

function renderCotizacion(ruta = '/cotizar') {
  return render(<MemoryRouter initialEntries={[ruta]}><Cotizacion /></MemoryRouter>);
}

function completarContacto() {
  fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'Ana Pérez' } });
  fireEvent.change(screen.getByLabelText('Correo'), { target: { value: 'ana@example.test' } });
  fireEvent.change(screen.getByLabelText('Teléfono'), { target: { value: '+56912345678' } });
  fireEvent.click(screen.getByRole('checkbox', { name: /acepto que la tienda use mis datos/i }));
}

const enviar = () => fireEvent.click(screen.getByRole('button', { name: 'Enviar solicitud' }));

describe('Formulario de cotización', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    configuracion.actual = { nombre_tienda: 'Tienda QA', cotizaciones_activas: true };
    // Como el backend: sin `todos` el catálogo llega paginado
    clienteAxios.get.mockImplementation((url) => Promise.resolve({ data: {
      'catalogo/productos/?todos=true': PRODUCTOS,
      'catalogo/productos/': { count: PRODUCTOS.length, results: PRODUCTOS }
    }[url] ?? [] }));
    clienteAxios.post.mockResolvedValue({ data: { mensaje: 'Recibimos tu solicitud.' } });
  });

  afterEach(() => cleanup());

  it('si la tienda no recibe cotizaciones lo dice y no muestra el formulario', () => {
    configuracion.actual = { cotizaciones_activas: false };
    renderCotizacion();
    expect(screen.getByText(/no está recibiendo cotizaciones/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Enviar solicitud' })).not.toBeInTheDocument();
  });

  it('ofrece solo los productos publicados y llega con el producto de la ficha elegido', async () => {
    renderCotizacion('/cotizar?producto=taza');

    expect(await screen.findByRole('option', { name: 'Taza de cerámica' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Producto en borrador' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Producto')).toHaveValue('taza');
  });

  it('el envío exige aceptar la Política de Privacidad, desmarcada por defecto', () => {
    renderCotizacion();
    const privacidad = screen.getByRole('checkbox', { name: /acepto que la tienda use mis datos/i });
    expect(privacidad).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Enviar solicitud' })).toBeDisabled();
  });

  it('una persona envía su solicitud y ve la confirmación', async () => {
    renderCotizacion('/cotizar?producto=taza');
    fireEvent.change(screen.getByLabelText('Cantidad'), { target: { value: '50' } });
    fireEvent.change(screen.getByLabelText(/personalización/i), { target: { value: 'Con el logo' } });
    completarContacto();
    enviar();

    expect(await screen.findByRole('status')).toHaveTextContent('Recibimos tu solicitud.');
    expect(clienteAxios.post).toHaveBeenCalledWith('ventas/cotizaciones/', expect.objectContaining({
      producto_id: 'taza', cantidad: 50, personalizacion: 'Con el logo', nombre: 'Ana Pérez',
      como_empresa: false, empresa: null, fecha_requerida: null, acepta_privacidad: true, sitio_web: ''
    }));
    // El formulario queda limpio para otra solicitud
    expect(screen.getByLabelText('Nombre')).toHaveValue('');
  });

  describe('fotos de la idea', () => {
    const foto = (nombre = 'idea.jpg', tipo = 'image/jpeg', bytes = 10) => new File(['x'.repeat(bytes)], nombre, { type: tipo });
    const adjuntar = (...archivos) => fireEvent.change(screen.getByLabelText(/fotos de tu idea/i), { target: { files: archivos } });
    const miniaturas = () => within(screen.getByRole('list', { name: 'Fotos adjuntas' })).getAllByRole('img');
    const sinMiniaturas = () => expect(screen.queryByRole('list', { name: 'Fotos adjuntas' })).not.toBeInTheDocument();

    beforeEach(() => {
      let numero = 0;
      URL.createObjectURL = vi.fn(() => `blob:vista-${numero++}`);
      URL.revokeObjectURL = vi.fn();
    });

    it('se envían con los datos como multipart y se pueden quitar antes', async () => {
      renderCotizacion('/cotizar?producto=taza');
      adjuntar(foto('idea.jpg'), foto('referencia.png', 'image/png'));
      expect(miniaturas()).toHaveLength(2);
      fireEvent.click(screen.getByRole('button', { name: 'Quitar la foto 2' }));
      expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:vista-1');
      completarContacto();
      enviar();

      expect(await screen.findByRole('status')).toHaveTextContent('Recibimos tu solicitud.');
      const [, cuerpo] = clienteAxios.post.mock.calls[0];
      expect(cuerpo).toBeInstanceOf(FormData);
      expect(JSON.parse(cuerpo.get('datos'))).toEqual(expect.objectContaining({ producto_id: 'taza', nombre: 'Ana Pérez' }));
      expect(cuerpo.getAll('fotos').map(archivo => archivo.name)).toEqual(['idea.jpg']);
      sinMiniaturas();
    });

    it('no acepta más de tres, ni otros formatos ni archivos de más de 5 MB', () => {
      renderCotizacion();
      adjuntar(foto('a.jpg'), foto('b.jpg'), foto('c.jpg'), foto('d.jpg'));
      expect(screen.getByRole('alert')).toHaveTextContent('hasta 3 fotos');

      adjuntar(foto('idea.gif', 'image/gif'));
      expect(screen.getByRole('alert')).toHaveTextContent('"idea.gif" no sirve');

      adjuntar(foto('enorme.jpg', 'image/jpeg', 5 * 1024 * 1024 + 1));
      expect(screen.getByRole('alert')).toHaveTextContent('"enorme.jpg" no sirve');
      sinMiniaturas();
    });

    it('con tres fotos ya no ofrece agregar más', () => {
      renderCotizacion();
      adjuntar(foto('a.jpg'), foto('b.jpg'), foto('c.jpg'));
      expect(miniaturas()).toHaveLength(3);
      expect(screen.queryByLabelText(/fotos de tu idea/i, { selector: 'input' })).not.toBeInTheDocument();
    });
  });

  it('una empresa con un RUT inválido ve el error junto al campo y no se envía', async () => {
    renderCotizacion('/cotizar?producto=taza');
    completarContacto();
    fireEvent.click(screen.getByRole('checkbox', { name: /cotizo para una empresa/i }));
    // Con los demás datos completos (si falta uno, el navegador no deja enviar y marca ese campo)
    const datos = { 'Razón social': 'Comercial Andes SpA', 'RUT de la empresa': '76.123.456-1', Giro: 'Regalos',
                    'Dirección comercial': 'Av. Providencia 1234', 'Correo para la factura': 'f@andes.test' };
    Object.entries(datos).forEach(([etiqueta, valor]) =>
      fireEvent.change(screen.getByLabelText(etiqueta), { target: { value: valor } }));
    enviar();

    expect(await screen.findByLabelText('RUT de la empresa')).toHaveAccessibleDescription(/dígito verificador/);
    expect(clienteAxios.post).not.toHaveBeenCalled();
  });

  it('muestra junto a cada campo los errores del servidor, también los de la empresa', async () => {
    clienteAxios.post.mockRejectedValue({ response: { status: 400, data: {
      telefono: 'Ingresa un teléfono chileno de 9 dígitos.',
      empresa: { giro: 'Este dato es obligatorio para la factura.' }
    } } });
    renderCotizacion('/cotizar?producto=taza');
    completarContacto();
    fireEvent.click(screen.getByRole('checkbox', { name: /cotizo para una empresa/i }));
    const datos = { 'Razón social': 'Comercial Andes SpA', 'RUT de la empresa': '76.123.456-0', Giro: 'x',
                    'Dirección comercial': 'Av. Providencia 1234', 'Correo para la factura': 'f@andes.test' };
    Object.entries(datos).forEach(([etiqueta, valor]) =>
      fireEvent.change(screen.getByLabelText(etiqueta), { target: { value: valor } }));
    enviar();

    await waitFor(() => expect(screen.getByLabelText('Teléfono'))
      .toHaveAccessibleDescription('Ingresa un teléfono chileno de 9 dígitos.'));
    expect(screen.getByLabelText('Giro')).toHaveAccessibleDescription('Este dato es obligatorio para la factura.');
  });

  it('avisa cuando se enviaron demasiadas solicitudes seguidas', async () => {
    clienteAxios.post.mockRejectedValue({ response: { status: 429, data: { detail: 'Request was throttled.' } } });
    renderCotizacion('/cotizar?producto=taza');
    completarContacto();
    enviar();

    expect(await screen.findByRole('alert')).toHaveTextContent(/muchas solicitudes seguidas/);
  });
});

describe('Panel: cotizaciones', () => {
  const COTIZACION = {
    id: 7, fecha_creacion: '2026-10-20T15:00:00Z', estado: 'NUEVA', estado_display: 'Nueva', nombre: 'Ana Pérez',
    correo: 'ana@example.test', telefono: '+56912345678', producto_id: 'taza', producto_nombre: 'Taza de cerámica',
    descripcion: '', cantidad: 50, personalizacion: 'Con el logo', fecha_requerida: '2026-11-05',
    datos_empresa: { razon_social: 'Comercial Andes SpA', rut: '76.123.456-0', giro: 'Regalos',
                     direccion: 'Av. Providencia 1234', correo: 'facturas@andes.test' }
  };

  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it('muestra cada solicitud con sus datos y la de la empresa', async () => {
    clienteAxios.get.mockResolvedValue({ data: { count: 1, results: [COTIZACION] } });
    render(<GestorCotizaciones />);

    expect(await screen.findByRole('heading', { name: '#7 · Taza de cerámica' })).toBeInTheDocument();
    expect(screen.getByText('05-11-2026')).toBeInTheDocument();
    expect(screen.getByText(/RUT 76.123.456-0/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'ana@example.test' })).toHaveAttribute('href', 'mailto:ana@example.test');
  });

  it('las fotos de la idea se piden con la sesión del admin y se ven en la tarjeta', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:foto-11');
    URL.revokeObjectURL = vi.fn();
    clienteAxios.get.mockImplementation((url) => Promise.resolve(url === 'ventas/admin/cotizaciones/7/fotos/11/'
      ? { data: new Blob(['jpg'], { type: 'image/jpeg' }) }
      : { data: { count: 1, results: [{ ...COTIZACION, fotos: [11] }] } }));
    const { unmount } = render(<GestorCotizaciones />);

    const foto = await screen.findByRole('img', { name: /Foto 1 de la cotización #7/ });
    expect(foto).toHaveAttribute('src', 'blob:foto-11');
    // Por la API (con el token), no por una URL pública de /media/
    expect(clienteAxios.get).toHaveBeenCalledWith('ventas/admin/cotizaciones/7/fotos/11/', { responseType: 'blob' });
    unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:foto-11');
  });

  it('la tienda cambia el estado y lo ve confirmado', async () => {
    clienteAxios.get.mockResolvedValue({ data: { count: 1, results: [COTIZACION] } });
    clienteAxios.patch.mockResolvedValue({ data: { ...COTIZACION, estado: 'RESPONDIDA', estado_display: 'Respondida' } });
    render(<GestorCotizaciones />);

    fireEvent.change(await screen.findByLabelText('Estado de la cotización #7'), { target: { value: 'RESPONDIDA' } });

    expect(await screen.findByRole('status')).toHaveTextContent('La cotización #7 quedó como Respondida.');
    expect(clienteAxios.patch).toHaveBeenCalledWith('ventas/admin/cotizaciones/7/', { estado: 'RESPONDIDA' });
    expect(screen.getByLabelText('Estado de la cotización #7')).toHaveValue('RESPONDIDA');
  });

  it('sin solicitudes lo dice', async () => {
    clienteAxios.get.mockResolvedValue({ data: { count: 0, results: [] } });
    render(<GestorCotizaciones />);
    expect(await screen.findByText('Todavía no hay solicitudes de cotización.')).toBeInTheDocument();
  });
});
